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
# Helper: extract user input safely from ADK Web state
# =============================================================================
def _extract_user_text(state: Any) -> Optional[str]:
    """
    Safely extract the conversational user text from ADK tool_context.state.
    Handles dict-like objects, State objects, or plain strings.
    """
    try:
        # If it's a dict-like (typical ADK case)
        if isinstance(state, dict):
            for key in ("input", "text", "message", "query", "user_message"):
                v = state.get(key)
                if isinstance(v, str) and v.strip():
                    return v.strip()

        # Some ADK State objects act like dataclasses
        if hasattr(state, "__dict__"):
            for key in ("input", "text", "message"):
                v = getattr(state, key, None)
                if isinstance(v, str) and v.strip():
                    return v.strip()

        # If it's already a clean string, just return it
        if isinstance(state, str):
            return state.strip()

        # Fallback — only if str(state) looks human
        s = str(state).strip()
        if s and not s.startswith("<") and "object at" not in s:
            return s

        return None
    except Exception as e:
        logger.warning(f"Failed to parse state input: {e}")
        return None


# =============================================================================
# Main HMM Call Prep Agent
# =============================================================================
async def hmm_get_data(topic: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Main entrypoint for the HMM Call Prep agent.

    Steps:
      1. Extract conversational input (string) safely from tool_context.state
      2. Validate input via validator.py
      3. Determine route (ID or Name+DOB)
      4. Call aggregator.get_patient_aggregated_data
      5. Return FastAPI backend response directly
    """
    logger.info("🟢 hmm_get_data called (topic=%s)", topic)
    state = getattr(tool_context, "state", {}) or {}

    # -------------------------------------------------------------------------
    # 1️⃣ Extract user message safely
    # -------------------------------------------------------------------------
    user_input = _extract_user_text(state)

    if not user_input:
        logger.warning("No valid conversational text found in tool_context.state.")
        return {
            "status": "error",
            "message": (
                "No recognizable input found. Please provide either "
                "Subscriber ID (#########/##) or 'First Last, MM-DD-YYYY'."
            ),
        }

    # Clean invisible chars and normalize slashes
    cleaned = user_input.replace("\u200b", "").replace("\uFEFF", "").replace("\\", "/").strip()
    logger.info(f"💬 User Input (cleaned): {cleaned}")

    # -------------------------------------------------------------------------
    # 2️⃣ Validate input via validator
    # -------------------------------------------------------------------------
    valid, payload, err = validate_input(cleaned)
    logger.info("🧩 Validator => valid=%s payload=%s err=%s", valid, payload, err)

    if not valid:
        logger.warning("Validation failed: %s", err)
        return {
            "status": "error",
            "message": err or "Input format invalid. Use ID (#########/##) or 'First Last, MM-DD-YYYY'.",
        }

    # -------------------------------------------------------------------------
    # 3️⃣ Determine input path and extract relevant parameters
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
        logger.info("✅ Path chosen: Name+DOB (%s %s, DOB=%s)", first_name, last_name, date_of_birth)
    else:
        logger.error("Validator returned unexpected method: %s", method)
        return {"status": "error", "message": "Unexpected validation result."}

    # -------------------------------------------------------------------------
    # 4️⃣ Call aggregator to fetch patient data
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
            logger.info("✅ Aggregator responded successfully.")
    except Exception as e:
        logger.exception("Error while fetching data from backend.")
        return {
            "status": "error",
            "message": "Failed to retrieve data from backend.",
            "detail": str(e),
        }

    # -------------------------------------------------------------------------
    # 5️⃣ Return backend response as-is (FastAPI already applies schema)
    # -------------------------------------------------------------------------
    if not result:
        logger.warning("No data returned from aggregator for given input.")
        return {"status": "error", "message": "No patient data found for provided input."}

    return result


# =============================================================================
# Register the agent
# =============================================================================
hmm_call_prep = Agent(
    name="hmm_call_prep",
    model="gemini-2.0-flash",
    description="Agent that validates conversational input and retrieves patient aggregated data for HMM call prep.",
    instruction=prompt.CALL_PREP_AGENT_PROMPT,
    tools=[hmm_get_data],
)
