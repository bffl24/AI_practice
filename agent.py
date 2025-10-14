# agent.py
import logging
from typing import Any, Dict, Optional, List

from pydantic import BaseModel, Field
from google.adk.agents import Agent
from google.adk.tools.tool_context import ToolContext

from . import prompt
from .tools.client import HealthcareApiClient
from .tools.aggregator import PatientDataAggregator
from .tools.validator import validate_input

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# -------------------------
# Pydantic response schemas
# -------------------------
class ErrorData(BaseModel):
    """Standard structure for error payloads."""
    message: str
    detail: Optional[Any] = None


class ResponseSchema(BaseModel):
    """Unified agent response model."""
    status: str = Field(..., description="Either 'success' or 'error'")
    topic: Optional[str] = Field(None, description="Topic requested by the user")
    data: Optional[Any] = Field(None, description="Payload for success or ErrorData for errors")
    candidates: Optional[List[Any]] = Field(None, description="Optional candidate list if multiple matches")


# -------------------------
# Main agent logic
# -------------------------
async def hmm_get_data(topic: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Main entrypoint for HMM Call Prep agent.

    Responsibilities:
      - Validate and normalize user input
      - Identify path type (ID or Name+DOB)
      - Pass only relevant fields to PatientDataAggregator.get_patient_aggregated_data()
      - Return a unified ResponseSchema
    """
    logger.info(f"--- hmm_get_data called (topic={topic}) ---")

    # Extract state context
    state = getattr(tool_context, "state", {}) or {}

    # -------------------------
    # Robust extraction of raw input (also handles 'topic' key)
    # -------------------------
    raw_text = None
    if isinstance(state, dict):
        # include common keys and topic as a fallback (your UI sometimes puts user text in 'topic')
        raw_text = (
            state.get("text")
            or state.get("query")
            or state.get("message")
            or state.get("input")
            or state.get("user_message")
            or state.get("topic")
        )
    else:
        # state might already be a raw string
        raw_text = state

    # Normalize and clean the raw string if present
    if isinstance(raw_text, str) and raw_text.strip():
        cleaned = raw_text.strip()
        # Remove common hidden characters and normalize slashes/backslashes
        cleaned = cleaned.replace("\u200b", "").replace("\uFEFF", "")
        cleaned = cleaned.replace("\u2215", "/").replace("\u2044", "/").replace("\\", "/")
        validator_input = cleaned
    else:
        # If there is no raw string, pass the whole dict for structured validation (subscriber/member fields)
        validator_input = state

    logger.debug("Validator input (repr): %r", validator_input)

    # 1) Validate input using the shared validator
    valid, payload, err = validate_input(validator_input)
    if not valid:
        logger.warning("Validation failed: %s", err)
        guidance = (
            "Input not recognized.\n\n"
            "Please provide ONE of the following formats:\n"
            "• Subscriber Path → 050028449/00 (9 digits '/' 2 digits) or 05002844900 (11 digits)\n"
            "• Name+DOB Path → First Last, MM-DD-YYYY (comma required; MM/DD/YYYY and YYYY-MM-DD accepted)\n\n"
            f"Details: {err}"
        )
        return ResponseSchema(
            status="error",
            topic=topic,
            data=ErrorData(message=guidance).dict(),
        ).dict()

    # 2) Identify which path we are using (ID or Name+DOB) and prepare aggregator params
    if payload["method"] == "id":
        subscriber_id = payload.get("subscriber_id")
        member_id = payload.get("member_id")
        first_name = last_name = date_of_birth = None
        logger.info(f"Validated Path 1 (ID): subscriber_id={subscriber_id}, member_id={member_id}")
    elif payload["method"] == "name_dob":
        first_name = payload.get("first_name")
        last_name = payload.get("last_name")
        date_of_birth = payload.get("dob")  # normalized MM-DD-YYYY
        subscriber_id = member_id = None
        logger.info(f"Validated Path 2 (Name+DOB): {first_name} {last_name}, DOB={date_of_birth}")
    else:
        logger.error(f"Unexpected validation method: {payload.get('method')}")
        return ResponseSchema(
            status="error",
            topic=topic,
            data=ErrorData(message="Unexpected validation method.").dict(),
        ).dict()

    # 3) Call aggregator and fetch patient data
    try:
        async with HealthcareApiClient() as client:
            aggregator = PatientDataAggregator(client)

            aggregated_data = await aggregator.get_patient_aggregated_data(
                subscriber_id=subscriber_id,
                member_id=member_id,
                first_name=first_name,
                last_name=last_name,
                date_of_birth=date_of_birth,
            )

            # Handle explicit aggregator error responses (preserve candidates if present)
            if isinstance(aggregated_data, dict) and aggregated_data.get("status") == "error":
                message = aggregated_data.get("data", "Unknown aggregator error")
                candidates = aggregated_data.get("candidates")
                logger.warning(f"Aggregator returned error: {message}")
                return ResponseSchema(
                    status="error",
                    topic=topic,
                    data=ErrorData(message=message).dict(),
                    candidates=candidates,
                ).dict()

    except Exception as e:
        logger.exception("Error while fetching aggregated data")
        return ResponseSchema(
            status="error",
            topic=topic,
            data=ErrorData(message="Failed to retrieve data", detail=str(e)).dict(),
        ).dict()

    # 4) Success — return the aggregated data directly
    logger.info(f"Returning aggregated data for topic={topic}")
    return ResponseSchema(status="success", topic=topic, data=aggregated_data).dict()


# -------------------------
# Agent registration
# -------------------------
hmm_call_prep = Agent(
    name="hmm_call_prep",
    model="gemini-2.0-flash",
    description="Agent that validates input and retrieves patient aggregated data for HMM call prep.",
    instruction=prompt.CALL_PREP_AGENT_PROMPT,
    tools=[hmm_get_data],
)
