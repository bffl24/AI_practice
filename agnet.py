import logging
from typing import Any, Dict

from google.adk.agents import Agent
from google.adk.tools.tool_context import ToolContext

from app.api_client.client import HealthcareAPIClient
from app.api_client.aggregator import PatientDataAggregator
from app.api_client.prompt import CALL_PREP_AGENT_PROMPT

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# ============================================================
# 3️⃣ Call aggregator (FAST API)
# ============================================================
async def hmm_get_data(topic: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Retrieve patient aggregated data from FastAPI backend for HMM call preparation.
    This agent assumes validated input is already present in tool_context.state.
    """
    logger.info(f"--- Tool : hmm_get_data called with topic={topic} ---")
    state = getattr(tool_context, "state", {}) or {}

    # Ensure state is populated by root_agent
    method = state.get("method")
    if not method:
        logger.warning("No validated context found in tool_context.state.")
        return {
            "status": "error",
            "data": "Missing validated input. Please run the root agent first.",
            "topic": topic,
        }

    # Extract parameters based on method
    if method == "id":
        subscriber_id = state.get("subscriber_id")
        member_id = state.get("member_id")
        first_name = last_name = date_of_birth = None
        logger.info(f"🧩 Using ID Path: Subscriber={subscriber_id}, Member={member_id}")
    else:
        subscriber_id = member_id = None
        first_name = state.get("first_name")
        last_name = state.get("last_name")
        date_of_birth = state.get("date_of_birth")
        logger.info(f"🧩 Using Name+DOB Path: {first_name} {last_name}, DOB={date_of_birth}")

    # ============================================================
    # 3️⃣ Call aggregator (FAST API)
    # ============================================================
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
            logger.info("✅ Aggregator call successful.")
    except Exception as e:
        logger.exception("❌ Error fetching data from PatientDataAggregator")
        return {"status": "error", "data": f"Backend request failed: {str(e)}", "topic": topic}

    if not patient_data:
        return {"status": "error", "data": "No patient data found for provided input.", "topic": topic}

    # Map topic -> response section
    topic_map = {
        "patient_info": patient_data.get("demographics"),
        "medical_history": patient_data.get("medical_history"),
        "recent_visits": patient_data.get("visits"),
        "status": patient_data.get("status"),
    }

    data_for_topic = topic_map.get(topic.lower(), patient_data)
    logger.info(f"✅ Returning data for topic={topic}")
    return {"status": "success", "data": data_for_topic, "topic": topic}


# ============================================================
# Agent registration
# ============================================================
hmm_call_prep = Agent(
    name="hmm_call_prep",
    model="gemini-2.0-flash",
    description=(
        "Fetches patient aggregated data from the FastAPI service for HMM Call Preparation. "
        "Expects validated input (Subscriber ID or Name+DOB) provided by the root agent."
    ),
    instruction=CALL_PREP_AGENT_PROMPT,
    tools=[hmm_get_data],
)
