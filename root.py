import logging
from typing import Any, Dict, Optional

from google.adk.agents import Agent
from google.adk.tools.tool_context import ToolContext

from sub_agents.hmm_call_prep.agent import hmm_call_prep  # adjust import path if different
from app.api_client.validator import validate_input       # your validator

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# ----------------------------------------------
# Helper: get user text from ToolContext safely
# ----------------------------------------------
def _extract_user_text(tool_context: ToolContext) -> Optional[str]:
    """
    Robustly pull the user's message from ToolContext. ADK can surface it in
    different places depending on version and runtime.
    """
    st = getattr(tool_context, "state", {}) or {}

    # 1) dict-like state keys
    if isinstance(st, dict):
        for k in ("input", "text", "message", "query", "user_message"):
            v = st.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        # nested conversation dict
        conv = st.get("conversation")
        if isinstance(conv, dict):
            for k in ("user_message", "text", "input"):
                v = conv.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()

    # 2) attribute-style state (dataclass-like)
    if st and not isinstance(st, dict) and hasattr(st, "__dict__"):
        for k in ("input", "text", "message", "user_message"):
            v = getattr(st, k, None)
            if isinstance(v, str) and v.strip():
                return v.strip()
        inner = getattr(st, "input", None)
        if inner is not None and hasattr(inner, "text"):
            t = getattr(inner, "text", None)
            if isinstance(t, str) and t.strip():
                return t.strip()

    # 3) some ADK builds put it on tool_context.input.text
    if hasattr(tool_context, "input") and hasattr(tool_context.input, "text"):
        t = getattr(tool_context.input, "text", None)
        if isinstance(t, str) and t.strip():
            return t.strip()

    return None


# ============================================================
# 2️⃣ Validate input via validator.py
# ============================================================
async def validate_and_delegate(tool_context: ToolContext) -> Dict[str, Any]:
    """
    Root agent:
    - Extract user text from ToolContext,
    - Validate with validate_input(...),
    - Store normalized values into tool_context.state,
    - Delegate to hmm_call_prep with a shared ToolContext.
    """
    logger.info("🟢 Root Agent: Starting validation and delegation flow.")
    state = getattr(tool_context, "state", {}) or {}

    user_text = _extract_user_text(tool_context)
    logger.info(f"🔍 extracted user_text={user_text!r}")

    if not user_text:
        return {
            "status": "error",
            "message": "No input detected. Please provide Subscriber ID (#########/##) or 'First Last, MM-DD-YYYY'."
        }

    valid, payload, err = validate_input(user_text)
    logger.info(f"🧩 validator => valid={valid}, payload={payload}, err={err}")

    if not valid:
        return {"status": "error", "message": err or "Input not recognized."}

    # Normalize state for sub-agent consumption
    method = payload.get("method")
    if method == "id":
        state.update({
            "method": "id",
            "subscriber_id": payload["subscriber_id"],
            "member_id": payload["member_id"],
        })
        state.pop("first_name", None)
        state.pop("last_name", None)
        state.pop("date_of_birth", None)
        logger.info(f"✅ ID path: {payload['subscriber_id']}/{payload['member_id']}")
    else:  # "name_dob"
        state.update({
            "method": "name_dob",
            "first_name": payload["first_name"],
            "last_name": payload["last_name"],
            "date_of_birth": payload["dob"],
        })
        state.pop("subscriber_id", None)
        state.pop("member_id", None)
        logger.info(f"✅ Name+DOB path: {payload['first_name']} {payload['last_name']} ({payload['dob']})")

    # Persist normalized state back on the original context
    tool_context.state = state
    logger.info(f"🧾 manager state before delegate: {tool_context.state}")

    # IMPORTANT: pass the SAME state dictionary to the sub-agent
    sub_ctx = ToolContext(state=tool_context.state)
    result = await hmm_call_prep.tools[0](topic="patient_info", tool_context=sub_ctx)
    return result


# ============================================================
# Agent registration
# ============================================================
root_agent = Agent(
    name="manager",
    model="gemini-2.0-flash",
    description=(
        "Validates user inputs (Subscriber ID or Name+DOB) and delegates to hmm_call_prep "
        "to retrieve patient aggregated data."
    ),
    instruction=(
        "Validate the user's identity input, write the normalized values into state, then call hmm_call_prep. "
        "Always include: 'While I strive for accuracy, please verify this information before use.'"
    ),
    sub_agents=[],
    tools=[validate_and_delegate],
)
