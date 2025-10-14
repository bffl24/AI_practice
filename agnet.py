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
    message: str
    detail: Optional[Any] = None


class ResponseSchema(BaseModel):
    status: str = Field(..., description="Either 'success' or 'error'")
    topic: Optional[str] = Field(None, description="Requested topic or slice")
    data: Optional[Any] = Field(None, description="Payload for success or ErrorData for errors")
    candidates: Optional[List[Any]] = Field(None, description="Optional candidate list if multiple matches")


# Allowed topic keys (if you want to return slices)
_ALLOWED_TOPIC_KEYS = {"demographics", "medications", "visits", "status"}


# -------------------------
# Main agent logic
# -------------------------
async def hmm_get_data(topic: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Entry point for HMM call-prep.

    Important: `topic` is NOT the user's message. It is only used to select a slice of the aggregated result.
    User input must come from tool_context.state (text/message/query/input/user_message).
    """
    logger.info("hmm_get_data called (topic=%s)", topic)
    state = getattr(tool_context, "state", {}) or {}

    # -------------------------
    # Extract user message from state (DO NOT use the 'topic' parameter as input)
    # -------------------------
    raw_text: Optional[str] = None
    if isinstance(state, dict):
        # NOTE: do NOT include state.get("topic") here. topic param is separate.
        raw_text = (
            state.get("text")
            or state.get("message")
            or state.get("query")
            or state.get("input")
            or state.get("user_message")
        )
    else:
        # state could already be a string
        raw_text = state

    # Normalize minor issues
    if isinstance(raw_text, str) and raw_text.strip():
        cleaned = raw_text.strip()
        cleaned = cleaned.replace("\u200b", "").replace("\uFEFF", "")  # remove zero-width/BOM
        cleaned = cleaned.replace("\\", "/")
        validator_input: Any = cleaned
    else:
        # No raw string found — pass the structured dict so validator can check structured fields
        validator_input = state

    logger.debug("Validator input (repr): %r", validator_input)

    # -------------------------
    # Validate input and unpack properly
    # -------------------------
    valid, payload, err = validate_input(validator_input)  # <- correct unpacking
    if not valid:
        logger.warning("Validation failed: %s", err)
        guidance = (
            "Input not recognized. Provide ONE of:\n"
            "- Subscriber path: 050028449/00 (9 digits '/' 2 digits) or 05002844900 (11 digits)\n"
            "- Name+DOB path: First Last, MM-DD-YYYY (comma required; MM/DD/YYYY and YYYY-MM-DD accepted)\n\n"
            f"Details: {err}"
        )
        return ResponseSchema(status="error", topic=topic, data=ErrorData(message=guidance).dict()).dict()

    # -------------------------
    # Exactly-one-path branching based on payload['method']
    # -------------------------
    method = payload.get("method")
    if method == "id":
        subscriber_id = payload.get("subscriber_id")
        member_id = payload.get("member_id")
        first_name = last_name = date_of_birth = None
        logger.info("Path chosen: ID (subscriber=%s member=%s)", subscriber_id, member_id)

    elif method == "name_dob":
        subscriber_id = member_id = None
        first_name = payload.get("first_name")
        last_name = payload.get("last_name")
        date_of_birth = payload.get("dob")  # normalized to MM-DD-YYYY by validator
        logger.info("Path chosen: Name+DOB (%s %s, %s)", first_name, last_name, date_of_birth)

    else:
        logger.error("Validator returned unexpected method: %s", method)
        return ResponseSchema(status="error", topic=topic, data=ErrorData(message="Unexpected validation method").dict()).dict()

    # -------------------------
    # Call the aggregator with only the relevant fields for the chosen path
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

            # No match -> return clear error
            if aggregated is None:
                logger.info("No patient found for provided identity.")
                return ResponseSchema(status="error", topic=topic, data=ErrorData(message="No patient found for provided identity.").dict()).dict()

            # Aggregator returned structured error -> propagate
            if isinstance(aggregated, dict) and aggregated.get("status") == "error":
                message = aggregated.get("data", "Unknown aggregator error")
                candidates = aggregated.get("candidates")
                logger.warning("Aggregator returned error: %s", message)
                return ResponseSchema(status="error", topic=topic, data=ErrorData(message=message).dict(), candidates=candidates).dict()

    except Exception as e:
        logger.exception("Aggregator call failed")
        return ResponseSchema(status="error", topic=topic, data=ErrorData(message="Failed to retrieve data", detail=str(e)).dict()).dict()

    # -------------------------
    # If topic is a known slice key return slice, otherwise return full payload
    # -------------------------
    requested_key = (topic or "").strip().lower()
    if requested_key in _ALLOWED_TOPIC_KEYS:
        slice_data = aggregated.get(requested_key)
        return ResponseSchema(status="success", topic=topic, data={requested_key: slice_data}).dict()

    # Default: return full aggregated payload
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
