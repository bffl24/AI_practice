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
    Entry point for HMM call-prep.

    Behavior:
      - Extract raw user input from tool_context.state (robust keys)
      - Validate input via tools.validator.validate_input()
      - Branch to exactly one path:
          * ID path: pass subscriber_id & member_id to the aggregator
          * Name+DOB path: pass first_name, last_name, date_of_birth to the aggregator
      - Call PatientDataAggregator.get_patient_aggregated_data(...) with only relevant fields
      - Return ResponseSchema dict
    """
    logger.info("hmm_get_data called (topic=%s)", topic)
    state = getattr(tool_context, "state", {}) or {}

    # -------------------------
    # Robust raw input extraction
    # -------------------------
    # Prefer explicit text/message keys; 'topic' is a fallback only because some UIs
    # put the user's message in state['topic']. If you can standardize the UI to
    # use 'text' or 'message', remove the 'topic' fallback.
    raw_text: Optional[str] = None
    if isinstance(state, dict):
        raw_text = (
            state.get("text")
            or state.get("message")
            or state.get("query")
            or state.get("input")
            or state.get("user_message")
            or state.get("topic")  # fallback for legacy UI behavior
        )
    else:
        raw_text = state  # state might already be a string

    # Normalize small issues (trim, normalize backslashes to forward slash, remove common zero-width)
    if isinstance(raw_text, str) and raw_text.strip():
        cleaned = raw_text.strip()
        cleaned = cleaned.replace("\u200b", "").replace("\uFEFF", "")
        cleaned = cleaned.replace("\\", "/")
        validator_input: Any = cleaned
    else:
        # if no raw string, pass the whole dict for structured validation paths
        validator_input = state

    logger.debug("Validator input (repr): %r", validator_input)

    # -------------------------
    # Validate input (must select exactly one path)
    # -------------------------
    valid, payload, err = validate_input(validator_input)
    if not valid:
        logger.warning("Validation failed: %s", err)
        guidance = (
            "Input not recognized.\n\n"
            "Provide ONE of the following formats:\n"
            "- Subscriber path: 050028449/00 (9 digits '/' 2 digits) or 05002844900 (11 digits)\n"
            "- Name+DOB path: First Last, MM-DD-YYYY (comma required; accepts MM/DD/YYYY or YYYY-MM-DD)\n\n"
            f"Details: {err}"
        )
        return ResponseSchema(status="error", topic=topic, data=ErrorData(message=guidance).dict()).dict()

    # -------------------------
    # Exactly-one-path branching
    # -------------------------
    if payload["method"] == "id":
        # Path A: subscriber + member
        subscriber_id = payload.get("subscriber_id")
        member_id = payload.get("member_id")
        first_name = last_name = date_of_birth = None
        logger.info("Chosen path=ID (subscriber=%s member=%s)", subscriber_id, member_id)

    elif payload["method"] == "name_dob":
        # Path B: name + dob
        subscriber_id = member_id = None
        first_name = payload.get("first_name")
        last_name = payload.get("last_name")
        date_of_birth = payload.get("dob")  # normalized by validator to MM-DD-YYYY
        logger.info("Chosen path=Name+DOB (%s %s, %s)", first_name, last_name, date_of_birth)

    else:
        logger.error("Validator returned unexpected method: %s", payload.get("method"))
        return ResponseSchema(status="error", topic=topic, data=ErrorData(message="Unexpected validation method").dict()).dict()

    # -------------------------
    # Call aggregator with only relevant fields
    # -------------------------
    try:
        async with HealthcareApiClient() as client:
            aggregator = PatientDataAggregator(client)

            aggregated = await aggregator.get_patient_aggregated_data(
                subscriber_id=subscriber_id,
                member_id=member_id,
                first_name=first_name,
                last_name=last_name,
                date_of_birth=date_of_birth,
            )

            # Aggregator returned no match
            if aggregated is None:
                logger.info("No patient found for provided identity")
                return ResponseSchema(status="error", topic=topic, data=ErrorData(message="No patient found for provided identity.").dict()).dict()

            # Aggregator returned an error-shaped dict -> propagate
            if isinstance(aggregated, dict) and aggregated.get("status") == "error":
                message = aggregated.get("data", "Unknown aggregator error")
                candidates = aggregated.get("candidates")
                logger.warning("Aggregator returned error: %s", message)
                return ResponseSchema(status="error", topic=topic, data=ErrorData(message=message).dict(), candidates=candidates).dict()

    except Exception as e:
        logger.exception("Aggregator call failed: %s", e)
        return ResponseSchema(status="error", topic=topic, data=ErrorData(message="Failed to retrieve data", detail=str(e)).dict()).dict()

    # -------------------------
    # Success: return aggregated payload
    # -------------------------
    logger.info("Returning aggregated payload")
    return ResponseSchema(status="success", topic=topic, data=aggregated).dict()


# -------------------------
# Agent registration
# -------------------------
hmm_call_prep = Agent(
    name="hmm_call_prep",
    model="gemini-2.0-flash",
    description="Validates input and calls get_patient_aggregated_data via two distinct paths.",
    instruction=prompt.CALL_PREP_AGENT_PROMPT,
    tools=[hmm_get_data],
)
