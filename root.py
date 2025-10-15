import logging
from typing import Any, Dict

from google.adk.agents import Agent
from google.adk.tools.tool_context import ToolContext

from sub_agents.hmm_call_prep import hmm_call_prep  # import the sub-agent
from app.api_client.validator import validate_input  # your existing validator

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# ============================================================
# 2️⃣ Validate input via validator.py
# ============================================================
async def validate_and_delegate(tool_context: ToolContext) -> Dict[str, Any]:
    """
    Root agent that validates the user input and delegates to hmm_call_prep.
    Ensures the sub-agent receives structured, validated input via state.
    """
    logger.info("🟢 Root Agent: Starting validation and delegation flow.")
    state = getattr(tool_context, "state", {}) or {}

    # Extract conversational text safely
    user_text = None
    for key in ("input", "text", "message", "query", "user_message"):
        if isinstance(state.get(key), str):
            user_text = state[key].strip()
            break

    if not user_text:
        logger.warning("No valid user input found in tool_context.state.")
        return {"status": "error", "message": "No input detected. Please provide subscriber ID or Name+DOB."}

    # Validate user input
    logger.info(f"🔹 Validating input: {user_text}")
    valid, payload, err = validate_input(user_text)

    if not valid:
        logger.warning(f"❌ Validation failed: {err}")
        return {"status": "error", "message": err}

    # Populate validated data in tool_context.state for hmm_call_prep
    method = payload.get("method")
    if method == "id":
        state.update({
            "method": "id",
            "subscriber_id": payload["subscriber_id"],
            "member_id": payload["member_id"]
        })
        state.pop("first_name", None)
        state.pop("last_name", None)
        state.pop("date_of_birth", None)
        logger.info(f"✅ Validated ID path: {payload['subscriber_id']}/{payload['member_id']}")
    else:
        state.update({
            "method": "name_dob",
            "first_name": payload["first_name"],
            "last_name": payload["last_name"],
            "date_of_birth": payload["dob"]
        })
        state.pop("subscriber_id", None)
        state.pop("member_id", None)
        logger.info(f"✅ Validated Name+DOB path: {payload['first_name']} {payload['last_name']} ({payload['dob']})")

    # Persist validated state
    tool_context.state = state
    logger.info("🔁 Updated tool_context.state with validated data.")

    # Delegate to hmm_call_prep for actual data retrieval
    logger.info("🧩 Delegating to hmm_call_prep...")
    result = await hmm_call_prep.tools[0](topic="patient_info", tool_context=tool_context)
    return result


# ============================================================
# Agent registration
# ============================================================
call_prep_manager = Agent(
    name="manager",
    model="gemini-2.0-flash",
    description=(
        "Root manager agent that validates user inputs and delegates tasks "
        "to the HMM Call Prep sub-agent for data aggregation."
    ),
    instruction="""
    You are the Manager Agent responsible for orchestrating data retrieval.
    1. Validate user inputs (Subscriber ID or Name+DOB).
    2. Update workflow state with validated info.
    3. Delegate to the hmm_call_prep sub-agent to fetch the actual data.
    Always include a note: "Please verify this information before use."
    """,
    sub_agents=[hmm_call_prep],
    tools=[validate_and_delegate],
)
root_agent = call_prep_manager
