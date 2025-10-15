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


# =============================================================================
# HMM Call Prep Agent
# =============================================================================

async def hmm_get_data(topic: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Main entry point for the HMM Call Prep agent.

    Responsibilities:
    - Extract conversational user input (ADK Web safe)
    - Validate input via validator.py
    - Identify one of two paths: ID or Name+DOB
    - Call FastAPI aggregator (get_patient_aggregated_data)
    - Return backend response directly (no schema wrapping)
    """
    logger.info("hmm_get_data called (topic=%s)", topic)
    state = getattr(tool_context, "state", {}) or {}

    # -------------------------------------------------------------------------
    # 1️⃣ Extract conversational input from ADK Web tool_context.state
    # -------------------------------------------------------------------------
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
        return {
            "status": "error",
            "message": "No input detected. Please provide either subscriber ID (#########/##) or 'First Last, MM-DD-YYYY'."
        }

    cleaned = raw_text.replace("\u200b", "").replace("\uFEFF", "").replace("\\", "/").strip()
    logger.info(f"User input (cleaned): {cleaned}")

    # -------------------------------------------------------------------------
    # 2️⃣ Validate input via validator
    # -------------------------------------------------------------------------
    valid, payload, err = validate_input(cleaned)
    logger.info("VALIDATOR OUTPUT => valid=%s payload=%s err=%s", valid, payload, err)

    if not valid:
        logger.warning("Validation failed: %s", err)
        return {
            "status": "error",
            "message": err or "Invalid input. Please use a valid ID or Name+DOB format."
        }

    # -------------------------------------------------------------------------
    # 3️⃣ Determine input path and extract parameters
    # -------------------------------------------------------------------------
    method = payload.get("method")
    if method == "id":
        subscriber_id = payload.get("subscriber_id")
        member_id = payload.get("member_id")
        first_name = last_name = date_of_birth = None
        logger.info("✅ Path chosen: ID (subscriber=%s, member=%s)", subscriber_id, member_id)
    elif method == "name_dob":
        subscriber_id = member_id = None
        first_name = payload.get("first_name")
        last_name = payload.get("last_name")
        date_of_birth = payload.get("dob")
        logger.info("✅ Path chosen: Name+DOB (%s %s, %s)", first_name, last_name, date_of_birth)
    else:
        logger.error("Validator returned unexpected method: %s", method)
        return {"status": "error", "message": "Unexpected validation method."}

    # -------------------------------------------------------------------------
    # 4️⃣ Call the aggregator to fetch data from FastAPI backend
    # -------------------------------------------------------------------------
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
            logger.info("Aggregator returned response successfully.")
    except Exception as e:
        logger.exception("Error while fetching aggregated data")
        return {
            "status": "error",
            "message": "Backend request failed while fetching patient data.",
            "detail": str(e)
        }

    # -------------------------------------------------------------------------
    # 5️⃣ Return backend result as-is (FastAPI already structures the response)
    # -------------------------------------------------------------------------
    if not result:
        logger.warning("No data returned from aggregator for provided identity.")
        return {"status": "error", "message": "No patient data found for the provided input."}

    return result


# =============================================================================
# Register the agent
# =============================================================================

hmm_call_prep = Agent(
    name="hmm_call_prep",
    model="gemini-2.0-flash",
    description="Validates conversational input and retrieves patient aggregated data for HMM call prep.",
    instruction=prompt.CALL_PREP_AGENT_PROMPT,
    tools=[hmm_get_data],
)
