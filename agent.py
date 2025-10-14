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
# Response schemas
# -------------------------
class ErrorData(BaseModel):
    message: str
    detail: Optional[Any] = None


class ResponseSchema(BaseModel):
    status: str = Field(..., description="Either 'success' or 'error'")
    topic: Optional[str] = Field(None)
    data: Optional[Any] = Field(None)
    candidates: Optional[List[Any]] = Field(None)


# -------------------------
# Main agent tool
# -------------------------
async def hmm_get_data(topic: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Validate input and take exactly one of two paths:
      - Path A (ID): subscriber_id + member_id -> call get_patient_aggregated_data(subscriber_id, member_id, None, None, None)
      - Path B (Name+DOB): first_name + last_name + dob -> call get_patient_aggregated_data(None, None, first_name, last_name, date_of_birth)

    The aggregator function (FastAPI) is the same; only the input fields differ.
    """
    logger.info("hmm_get_data called (topic=%s)", topic)
    state = getattr(tool_context, "state", {}) or {}

    # Extract raw user text from common keys (topic fallback included for legacy UI)
    raw_text = None
    if isinstance(state, dict):
        raw_text = (
            state.get("text")
            or state.get("message")
            or state.get("query")
            or state.get("input")
            or state.get("user_message")
            or state.get("topic")
        )
    else:
        raw_text = state

    # If a raw string was found, normalize basic unicode slashes and trim
    if isinstance(raw_text, str) and raw_text.strip():
        validator_input: Any = raw_text.strip().replace("\u200b", "").replace("\uFEFF", "").replace("\\", "/")
    else:
        # if no raw string, pass through the dict to support structured inputs
        validator_input = state

    logger.debug("Validator input (repr): %r", validator_input)

    # Validate input (validator will return payload with method "id" or "name_dob")
    valid, payload, err = validate_input(validator_input)
    if not valid:
        logger.warning("Validation failed: %s", err)
        guidance = (
            "Input not recognized. Send ONE of:\n"
            "- Subscriber path: 050028449/00  (or 11 digits 05002844900)\n"
            "- Name+DOB path: First Last, MM-DD-YYYY (comma required; MM/DD/YYYY & YYYY-MM-DD accepted)\n"
            f"Details: {err}"
        )
        return ResponseSchema(status="error", topic=topic, data=ErrorData(message=guidance).dict()).dict()

    # Exactly-one-path branching
    if payload["method"] == "id":
        # Path A: use only subscriber_id & member_id
        subscriber_id = payload["subscriber_id"]
        member_id = payload["member_id"]
        first_name = last_name = date_of_birth = None
        logger.info("Chosen path: ID (subscriber=%s, member=%s)", subscriber_id, member_id)

    else:
        # Path B: use only first_name, last_name, dob
        subscriber_id = member_id = None
        first_name = payload["first_name"]
        last_name = payload["last_name"]
        date_of_birth = payload["dob"]  # normalized by validator to MM-DD-YYYY
        logger.info("Chosen path: Name+DOB (%s %s, %s)", first_name, last_name, date_of_birth)

    # Call the single aggregator function with only the relevant fields
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
                return ResponseSchema(status="error", topic=topic, data=ErrorData(message="No patient found.").dict()).dict()

            # If aggregator itself returned a structured error, propagate it
            if isinstance(aggregated, dict) and aggregated.get("status") == "error":
                return ResponseSchema(
                    status="error",
                    topic=topic,
                    data=ErrorData(message=aggregated.get("data", "Aggregator error")).dict(),
                    candidates=aggregated.get("candidates"),
                ).dict()

    except Exception as e:
        logger.exception("Aggregator call failed")
        return ResponseSchema(status="error", topic=topic, data=ErrorData(message="Failed to retrieve data", detail=str(e)).dict()).dict()

    # Success: return entire aggregated payload
    return ResponseSchema(status="success", topic=topic, data=aggregated).dict()


# -------------------------
# Register agent
# -------------------------
hmm_call_prep = Agent(
    name="hmm_call_prep",
    model="gemini-2.0-flash",
    description="Validates input and calls get_patient_aggregated_data via two distinct paths.",
    instruction=prompt.CALL_PREP_AGENT_PROMPT,
    tools=[hmm_get_data],
)
