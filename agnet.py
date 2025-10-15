import logging
import asyncio
from typing import Any, Dict, Optional

from google.adk.agents import Agent
from google.adk.tools.tool_context import ToolContext

# <-- your existing validator.py

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------
# Helper: ensure canonical user input from ADK tool_context.state
# ---------------------------------------------------------------------
def ensure_state_consistency(tool_context: ToolContext) -> Optional[str]:
    """
    Extract a conversational user input string from tool_context.state.
    This guarantees validate_input() always receives a plain string.
    """
    try:
        state = getattr(tool_context, "state", {}) or {}
        if not isinstance(state, dict):
            try:
                state = dict(state.__dict__)
            except Exception:
                state = {"_repr": str(state)}

        # Look for user input in common keys
        user_text = None
        for key in ("input", "text", "message", "query", "user_message"):
            v = state.get(key)
            if isinstance(v, str) and v.strip():
                user_text = v.strip()
                break
            if isinstance(v, dict):
                for sub in ("text", "user_message"):
                    sv = v.get(sub)
                    if isinstance(sv, str) and sv.strip():
                        user_text = sv.strip()
                        break
                if user_text:
                    break

        # Fallback for nested "conversation" dicts
        if not user_text:
            conv = state.get("conversation")
            if isinstance(conv, dict):
                for sub in ("user_message", "text"):
                    sv = conv.get(sub)
                    if isinstance(sv, str) and sv.strip():
                        user_text = sv.strip()
                        break

        # Fallback for object with attributes
        if not user_text and hasattr(tool_context, "state"):
            st = getattr(tool_context, "state")
            if hasattr(st, "__dict__"):
                for attr in ("input", "text", "message", "user_message"):
                    v = getattr(st, attr, None)
                    if isinstance(v, str) and v.strip():
                        user_text = v.strip()
                        break
                if not user_text and hasattr(st, "input"):
                    inner = getattr(st, "input", None)
                    if hasattr(inner, "text"):
                        t = getattr(inner, "text", None)
                        if isinstance(t, str) and t.strip():
                            user_text = t.strip()

        # As a last resort, use safe str()
        if not user_text:
            s = str(state).strip()
            if s and not s.startswith("<") and "object at" not in s:
                user_text = s

        if user_text:
            state["input"] = user_text
            tool_context.state = state
            return user_text
        return None

    except Exception as e:
        logger.warning("Failed to normalize tool_context.state: %s", e)
        return None


# ---------------------------------------------------------------------
# Main agent function
# ---------------------------------------------------------------------
async def hmm_get_data(topic: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Gather patient data for HMM call preparation using FastAPI service.
    Integrates validator-based input parsing for subscriber/member or Name+DOB.
    """
    logger.info(f"--- Tool : hmm_get_data called with topic: {topic} ---")

    # -----------------------------------------------------------------
    # 1️⃣ Normalize and extract user input
    # -----------------------------------------------------------------
    user_input = ensure_state_consistency(tool_context)
    if not user_input:
        logger.warning("No valid conversational text found in state.")
        return {
            "status": "error",
            "data": "No input detected. Please provide subscriber ID (#########/##) or 'First Last, MM-DD-YYYY'.",
            "topic": topic,
        }

    cleaned = user_input.replace("\u200b", "").replace("\uFEFF", "").replace("\\", "/").strip()
    logger.info(f"User Input (cleaned): {cleaned}")

    # -----------------------------------------------------------------
    # 2️⃣ Validate input via validator.py
    # -----------------------------------------------------------------
    valid, payload, err = validate_input(cleaned)
    if not valid:
        logger.warning(f"Validation failed: {err}")
        return {"status": "error", "data": err or "Invalid input format.", "topic": topic}

    # Extract route
    method = payload.get("method")
    if method == "id":
        subscriber_id = payload.get("subscriber_id")
        member_id = payload.get("member_id")
        first_name = last_name = date_of_birth = None
        logger.info(f"Validated ID path → Subscriber: {subscriber_id}, Member: {member_id}")
    elif method == "name_dob":
        subscriber_id = member_id = None
        first_name = payload.get("first_name")
        last_name = payload.get("last_name")
        date_of_birth = payload.get("dob")
        logger.info(f"Validated Name+DOB path → {first_name} {last_name}, DOB={date_of_birth}")
    else:
        logger.error("Validator returned unknown method.")
        return {"status": "error", "data": "Unexpected validation output.", "topic": topic}

    # -----------------------------------------------------------------
    # 3️⃣ Call aggregator (FAST API)
    # -----------------------------------------------------------------
    try:
        async with HealthcareAPIClient() as client:
            aggregator = PatientDataAggregator(client)
            patient_data = await aggregator.get_patient_aggregated_data(
                subscriber_id=subscriber_id,
                member_id=member_id,
                first_name=first_name,
                last_name=last_name,
                date_of_birth=date_of_birth,
            )
    except Exception as e:
        logger.exception("Error fetching data from PatientDataAggregator")
        return {
            "status": "error",
            "data": f"Failed to retrieve data: {str(e)}",
            "topic": topic,
        }

    if not patient_data:
        return {"status": "error", "data": f"No data returned from backend.", "topic": topic}

    # -----------------------------------------------------------------
    # 4️⃣ Extract data based on topic (if provided)
    # -----------------------------------------------------------------
    topic_map = {
        "patient_info": patient_data.get("demographics"),
        "medical_history": patient_data.get("medical_history"),
        "recent_visits": patient_data.get("visits"),
        "status": patient_data.get("status"),
    }

    data_for_topic = topic_map.get(topic.lower())
    if not data_for_topic:
        return {"status": "error", "data": f"Topic '{topic}' not found.", "topic": topic}

    logger.info(f"--- Tool : hmm_get_data completed successfully for topic: {topic} ---")
    return {"status": "success", "data": data_for_topic, "topic": topic}


# ---------------------------------------------------------------------
# Agent registration
# ---------------------------------------------------------------------
hmm_call_prep = Agent(
    name="hmm_call_prep",
    model="gemini-2.0-flash",
    description="Validates conversational input and retrieves patient aggregated data for HMM call prep.",
    instruction=prompt.CALL_PREP_AGENT_PROMPT,
    tools=[hmm_get_data],
)
