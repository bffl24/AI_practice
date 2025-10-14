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
    topic: Optional[str] = Field(None, description="Requested topic/slice")
    data: Optional[Any] = Field(None, description="Payload for success or ErrorData for errors")
    candidates: Optional[List[Any]] = Field(None, description="Optional candidate list if multiple matches")


# Allowed topic keys for returning slices (optional)
_ALLOWED_TOPIC_KEYS = {"demographics", "medications", "visits", "status"}


# -------------------------
# Main agent logic (ADK-web safe)
# -------------------------
async def hmm_get_data(topic: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    HMM call-prep entrypoint.

    - Extracts user input from tool_context.state in ADK Web (safe keys).
    - Validates via tools.validator.validate_input().
    - Branches exactly one path: ID or Name+DOB.
    - Calls PatientDataAggregator.get_patient_aggregated_data(...) with only relevant fields.
    - Returns ResponseSchema (pydantic) dict.
    """
    logger.info("hmm_get_data called (topic=%s)", topic)
    state = getattr(tool_context, "state", {}) or {}

    # -------------------------
    # ADK-web-safe extraction: DO NOT use the 'topic' parameter as user input
    # -------------------------
    raw_text: Optional[str] = None
    if isinstance(state, dict):
        # ADK web commonly uses "input" or "text", but check a few keys
        for key in ("input", "text", "message", "query", "user_message"):
            val = state.get(key)
            if isinstance(val, str) and val.strip():
                raw_text = val.strip()
                break
    else:
        # state could be a plain string in some integrations
        raw_text = str(state).strip() if state else None

    # If we found a raw string, clean it (normalize slashes, remove zero-width)
    if isinstance(raw_text, str) and raw_text:
        cleaned = raw_text.replace("\u200b", "").replace("\uFEFF", "").replace("\\", "/").strip()
        validator_input: Any = cleaned
    else:
        # fallback: pass the structured dict to the validator for structured fields
        validator_input = state

    logger.debug("Validator input (repr): %r", validator_input)

    # -------------------------
    # Validate input and unpack results
    # -------------------------
    valid, payload, err = validate_input(validator_input)
    if not valid:
        logger.warning("Validation failed: %s", err)
        guidance = (
            "Input not recognized. Provide ONE of:\n"
            "- Subscriber path: 050028449/00  (9 digits '/' 2 digits) or 05002844900 (11 digits)\n"
            "- Name+DOB path: First Last, MM-DD-YYYY (comma required; MM/DD/YYYY and YYYY-MM-DD accepted)\n\n"
            f"Details: {err}"
        )
        return ResponseSchema(status="error", topic=topic, data=ErrorData(message=guidance).dict()).dict()

    # -------------------------
    # Exactly-one-path branching based on payload["method"]
    # -------------------------
    method = payload.get("method")
    if method == "id":
        # ID path - only subscriber_id + member_id are populated
        subscriber_id = payload.get("subscriber_id")
        member_id = payload.get("member_id")
        first_name = last_name = date_of_birth = None
        logger.info("Path chosen: ID (subscriber=%s member=%s)", subscriber_id, member_id)

    elif method == "name_dob":
        # Name+DOB path - only first_name, last_name, date_of_birth are populated
        subscriber_id = member_id = None
        first_name = payload.get("first_name")
        last_name = payload.get("last_name")
        date_of_birth = payload.get("dob")  # normalized by validator to MM-DD-YYYY
        logger.info("Path chosen: Name+DOB (%s %s, %s)", first_name, last_name, date_of_birth)

    else:
        logger.error("Validator returned unexpected method: %s", method)
        return ResponseSchema(status="error", topic=topic, data=ErrorData(message="Unexpected validation method").dict()).dict()

    # -------------------------
    # Call the aggregator with only relevant fields
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

            # No match -> explicit error
            if aggregated is None:
                logger.info("No patient found for provided identity")
                return ResponseSchema(
                    status="error",
                    topic=topic,
                    data=ErrorData(message="No patient found for provided identity.").dict()
                ).dict()

            # Aggregator returned structured error -> propagate with candidates
            if isinstance(aggregated, dict) and aggregated.get("status") == "error":
                message = aggregated.get("data", "Unknown aggregator error")
                candidates = aggregated.get("candidates")
                logger.warning("Aggregator returned error: %s", message)
                return ResponseSchema(
                    status="error",
                    topic=topic,
                    data=ErrorData(message=message).dict(),
                    candidates=candidates,
                ).dict()

    except Exception as e:
        logger.exception("Aggregator call failed")
        return ResponseSchema(
            status="error",
            topic=topic,
            data=ErrorData(message="Failed to retrieve data", detail=str(e)).dict()
        ).dict()

    # -------------------------
    # If a named topic slice was requested (demographics/medications/visits/status),
    # return only that slice. Otherwise return the full aggregated payload.
    # -------------------------
    requested_key = (topic or "").strip().lower()
    if requested_key in _ALLOWED_TOPIC_KEYS:
        data_slice = aggregated.get(requested_key)
        return ResponseSchema(status="success", topic=topic, data={requested_key: data_slice}).dict()

    return ResponseSchema(status="success", topic=topic, data=aggregated).dict()


# -------------------------
# Agent registration
# -------------------------
hmm_call_prep = Agent(
    name="hmm_call_prep",
    model="gemini-2.0-flash",
    description="Validates ADK Web input and retrieves patient aggregated data for HMM call prep.",
    instruction=prompt.CALL_PREP_AGENT_PROMPT,
    tools=[hmm_get_data],
)
