# agent.py
import logging
import re
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
# Pydantic Response Schemas
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
# Helper: extract validator input robustly
# -------------------------
def _extract_validator_input(raw_state: Any) -> Optional[Any]:
    """
    Given the incoming tool state (which may be a string, dict, ToolContext-like object, etc.),
    extract either:
      - a clean text string to validate, or
      - a dict-like structure containing structured identity fields.

    Returns None if nothing usable is found.
    """
    # 1) If already a trimmed string
    if isinstance(raw_state, str):
        s = raw_state.strip()
        return s if s else None

    # 2) If dict-like, prefer explicit text fields; otherwise, return dict if it contains identity keys
    if isinstance(raw_state, dict):
        for k in ("text", "message", "query", "input"):
            v = raw_state.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        # If no free text, but structured identity keys exist, pass the dict through
        structured_keys = {
            "member_id", "subscriber_id", "first_name", "last_name", "dob",
            "date_of_birth", "member", "subscriber", "suffix"
        }
        if any(key in raw_state for key in structured_keys):
            return raw_state
        return None

    # 3) If object with .state or .text attribute (ToolContext-like), inspect those
    try:
        if hasattr(raw_state, "state"):
            return _extract_validator_input(getattr(raw_state, "state"))
        if hasattr(raw_state, "text"):
            t = getattr(raw_state, "text")
            if isinstance(t, str) and t.strip():
                return t.strip()
    except Exception:
        pass

    # 4) Last-resort heuristic: convert to string and accept if it looks like a meaningful payload
    try:
        s = str(raw_state).strip()
        if not s:
            return None
        # Heuristic: contains digits + slash OR contains comma (name,dob)
        if (re.search(r'\d', s) and ("/" in s or re.search(r'\d{11}', s))) or ("," in s and re.search(r'[A-Za-z]', s)):
            return s
    except Exception:
        pass

    return None


# -------------------------
# Main Agent Logic
# -------------------------
async def hmm_get_data(topic: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Main entrypoint for HMM Call Prep agent.

    Steps:
      1. Extract usable input (string or dict) from tool_context.state
      2. Validate using validate_input()
      3. Branch on the returned path (id vs name_dob)
      4. Call aggregator.get_patient_aggregated_data(...) with only relevant fields
      5. Return standardized ResponseSchema as dict()
    """
    logger.info(f"--- hmm_get_data called (topic={topic}) ---")

    state = getattr(tool_context, "state", {}) or {}

    # Extract the validator input robustly
    validator_input = _extract_validator_input(state)
    logger.debug("Validator input (repr): %r", validator_input)

    if validator_input is None:
        guidance = (
            "Input not recognized. Please provide ONE of the following:\n"
            "• Subscriber Path → 9digits/2digits (e.g., 050028449/00) or 11 digits (e.g., 05002844900)\n"
            "• Name+DOB Path → First Last, MM-DD-YYYY (comma required; accepts MM/DD/YYYY or YYYY-MM-DD)\n"
        )
        return ResponseSchema(status="error", topic=topic, data=ErrorData(message=guidance).dict()).dict()

    # Validate the extracted input (string or dict)
    valid, payload, err = validate_input(validator_input)
    if not valid:
        guidance = (
            "Input was not recognized. Please provide ONE of the following formats:\n"
            "• Subscriber Path → 9digits/2digits (e.g., 050028449/00) or 11 digits (e.g., 05002844900)\n"
            "• Name+DOB Path → First Last, MM-DD-YYYY (comma required; accepts MM/DD/YYYY or YYYY-MM-DD)\n"
            f"Validation details: {err}"
        )
        logger.warning("Validation failed: %s (input=%r)", err, validator_input)
        return ResponseSchema(status="error", topic=topic, data=ErrorData(message=guidance).dict()).dict()

    # Branch by path
    if payload["method"] == "id":
        subscriber_id = payload.get("subscriber_id")
        member_id = payload.get("member_id")
        first_name = last_name = date_of_birth = None
        logger.info("Using ID path: subscriber_id=%s, member_id=%s", subscriber_id, member_id)
    elif payload["method"] == "name_dob":
        first_name = payload.get("first_name")
        last_name = payload.get("last_name")
        date_of_birth = payload.get("dob")  # normalized to MM-DD-YYYY
        subscriber_id = member_id = None
        logger.info("Using Name+DOB path: %s %s, DOB=%s", first_name, last_name, date_of_birth)
    else:
        logger.error("Unexpected payload method: %s", payload.get("method"))
        return ResponseSchema(status="error", topic=topic, data=ErrorData(message="Unexpected validation result.").dict()).dict()

    # Call aggregator
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

            # Propagate aggregator error-shaped responses
            if isinstance(aggregated_data, dict) and aggregated_data.get("status") == "error":
                message = aggregated_data.get("data", "Unknown aggregator error")
                candidates = aggregated_data.get("candidates")
                logger.warning("Aggregator returned error: %s", message)
                return ResponseSchema(
                    status="error",
                    topic=topic,
                    data=ErrorData(message=message).dict(),
                    candidates=candidates,
                ).dict()

    except Exception as e:
        logger.exception("Exception while fetching aggregated data")
        return ResponseSchema(
            status="error",
            topic=topic,
            data=ErrorData(message="Failed to retrieve data", detail=str(e)).dict(),
        ).dict()

    # Success
    logger.info("Returning aggregated data for topic=%s", topic)
    return ResponseSchema(status="success", topic=topic, data=aggregated_data).dict()


# -------------------------
# Agent Registration
# -------------------------
hmm_call_prep = Agent(
    name="hmm_call_prep",
    model="gemini-2.0-flash",
    description="Agent that validates input and retrieves patient aggregated data for HMM call prep.",
    instruction=prompt.CALL_PREP_AGENT_PROMPT,
    tools=[hmm_get_data],
)
