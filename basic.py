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
    Simplified agent that uses topic directly.
    FORMAT 1: 050018449/00                -> ID path
    FORMAT 2: raja,panda,04-22-1980       -> Name+DOB path
    """
    logger.info(f"--- Tool : hmm_get_data called with topic={topic} ---")

    # Default values
    subscriber_id = member_id = first_name = last_name = date_of_birth = None

    # ------------------------------------------------------------
    # Case 1️⃣ : ID Path (SubscriberID/MemberID)
    # ------------------------------------------------------------
    if "/" in topic and topic.replace("/", "").isdigit():
        parts = topic.split("/")
        if len(parts) == 2:
            subscriber_id = parts[0]
            member_id = parts[1]
            logger.info(f"Detected ID Path: subscriber_id={subscriber_id}, member_id={member_id}")
        else:
            return {"status": "error", "data": "Invalid ID format. Expected #########/##", "topic": topic}

    # ------------------------------------------------------------
    # Case 2️⃣ : Name + DOB Path (first,last,mm-dd-yyyy)
    # ------------------------------------------------------------
    elif "," in topic:
        parts = topic.split(",")
        if len(parts) == 3:
            first_name = parts[0].strip()
            last_name = parts[1].strip()
            date_of_birth = parts[2].strip()
            logger.info(f"Detected Name+DOB Path: {first_name} {last_name}, DOB={date_of_birth}")
        else:
            return {"status": "error", "data": "Invalid Name+DOB format. Expected first,last,mm-dd-yyyy", "topic": topic}
    else:
        return {
            "status": "error",
            "data": "Input not recognized. Expected '#########/##' or 'first,last,mm-dd-yyyy'.",
            "topic": topic,
        }

    # ------------------------------------------------------------
    # Call FastAPI Aggregator
    # ------------------------------------------------------------
    try:
        async with HealthcareAPIClient() as client:
            aggregator = PatientDataAggregator(client)
            result = await aggregator.get_patient_aggregated_data(
                subscriber_id=subscriber_id,
                member_id=member_id,
                first_name=first_name,
                last_name=last_name,
                date_of_birth=date_of_birth,
            )
            logger.info("✅ Aggregator call completed successfully.")
    except Exception as e:
        logger.exception("❌ Error while calling PatientDataAggregator")
        return {"status": "error", "data": f"Backend call failed: {str(e)}", "topic": topic}

    if not result:
        return {"status": "error", "data": "No data found for the given input.", "topic": topic}

    return {"status": "success", "data": result, "topic": topic}


# ============================================================
# Agent registration
# ============================================================
hmm_call_prep = Agent(
    name="hmm_call_prep",
    model="gemini-2.0-flash",
    description="Minimal HMM Call Prep agent. Detects input type from topic and fetches data.",
    instruction=CALL_PREP_AGENT_PROMPT,
    tools=[hmm_get_data],
)
