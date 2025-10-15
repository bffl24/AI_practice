# agent.py
import logging
from typing import Any, Dict, Optional

from google.adk.agents import Agent
from google.adk.tools.tool_context import ToolContext

from . import prompt
from .tools.client import HealthcareApiClient
from .tools.aggregator import PatientDataAggregator
from .tools.validator import validate_input

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


async def hmm_get_data(topic: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    HMM call-prep entrypoint.

    - Extract conversational user text from ADK Web tool_context.state (input/text/message).
    - Validate with validate_input (conversational-only).
    - Branch to exactly one path (ID or name_dob).
    - Call aggregator.get_patient_aggregated_data with only the relevant fields.
    - Return backend (FastAPI) response directly (pass-through).
    """
    logger.info("hmm_get_data called (topic=%s)", topic)
    state = getattr(tool_context, "state", {}) or {}

    # ADK-web-safe extraction: check common keys for conversational input
    raw_text: Optional[str] = None
    if isinstance(state, dict):
        for key in ("input", "text", "message", "query", "user_message"):
            v = state.get(key)
            if isinstance(v, str) and v.strip():
                raw_text = v.strip()
                break
    else:
        raw_text = str(state).strip() if state else None

    if not raw_text:
        logger.warning("No conversational text found in tool_context.state.")
        return {"status": "error", "message": "No user message found. Provide subscriber ID or 'First Last, MM-DD-YYYY'."}

    # Normalize minor artifacts
    cleaned = raw_text.replace("\u200b", "").replace("\uFEFF", "").replace("\\", "/").strip()
    logger.debug("Cleaned user input: %s", cleaned)

    # Validate
    valid, payload, err = validate_input(cleaned)
    if not valid:
        logger.warning("Validation failed: %s", err)
        return {"status": "error", "message": err}

    # Branch to exactly one path
    method = payload.get("method")
    if method == "id":
        subscriber_id = payload.get("subscriber_id")
        member_id = payload.get("member_id")
        first_name = last_name = date_of_birth = None
        logger.info("Validated ID path: subscriber=%s member=%s", subscriber_id, member_id)
    elif method == "name_dob":
        subscriber_id = member_id = None
        first_name = payload.get("first_name")
        last_name = payload.get("last_name")
        date_of_birth = payload.get("dob")
        logger.info("Validated Name+DOB path: %s %s, DOB=%s", first_name, last_name, date_of_birth)
    else:
        logger.error("Validator returned unknown method: %s", method)
        return {"status": "error", "message": "Unexpected validation output."}

    # Call aggregator and return FastAPI response directly
    try:
        async with HealthcareApiClient() as client:
            aggregator = PatientDataAggregator(client)
            result = await aggregator.get_patient_aggregated_data(
                subscriber_id=subscriber_id,
                member_id=member_id,
                first_name=first_name,
                last_name=last_name,
                date_of_birth=date_of_birth,
            )
    except Exception as exc:
        logger.exception("Aggregator call failed")
        return {"status": "error", "message": "Failed to retrieve data from backend.", "detail": str(exc)}

    # If aggregator returns a dict with 'status' or error structure, pass as-is
    return result
