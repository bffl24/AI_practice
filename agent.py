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
# 🧠 Pydantic Response Schemas
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
# ⚙️ Main Agent Logic
# -------------------------
async def hmm_get_data(topic: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Main entrypoint for HMM Call Prep agent.

    Responsibilities:
      ✅ Validate and normalize user input
      ✅ Pass required fields to PatientDataAggregator.get_patient_aggregated_data()
      ✅ Return unified ResponseSchema
    """

    logger.info(f"--- hmm_get_data called (topic={topic}) ---")

    # Extract state context
    state = getattr(tool_context, "state", {}) or {}

    # 1️⃣ Validate input
    valid, payload, err = validate_input(state)
    if not valid:
        logger.warning(f"Validation failed: {err}")
        return ResponseSchema(
            status="error",
            topic=topic,
            data=ErrorData(message=err).dict(),
        ).dict()

    # 2️⃣ Prepare parameters for the aggregator (only the required fields)
    if payload["method"] == "id":
        subscriber_id = payload.get("subscriber_id")
        member_id = payload.get("member_id")
        first_name = last_name = date_of_birth = None
        logger.info(f"Validated Path 1 (IDs): subscriber={subscriber_id}, member={member_id}")
    else:
        first_name = payload.get("first_name")
        last_name = payload.get("last_name")
        date_of_birth = payload.get("dob")
        subscriber_id = member_id = None
        logger.info(f"Validated Path 2 (Name+DOB): {first_name} {last_name}, DOB={date_of_birth}")

    # 3️⃣ Call aggregator
    try:
        async with HealthcareApiClient() as client:
            aggregator = PatientDataAggregator(client)

            # Direct call to new simplified function
            aggregated_data = await aggregator.get_patient_aggregated_data(
                subscriber_id=subscriber_id,
                member_id=member_id,
                first_name=first_name,
                last_name=last_name,
                date_of_birth=date_of_birth,
            )

            # Handle explicit error responses if aggregator returns them
            if isinstance(aggregated_data, dict) and aggregated_data.get("status") == "error":
                logger.warning(f"Aggregator returned error: {aggregated_data.get('data')}")
                return ResponseSchema(
                    status="error",
                    topic=topic,
                    data=ErrorData(message=aggregated_data.get("data", "Unknown error")).dict(),
                    candidates=aggregated_data.get("candidates"),
                ).dict()

    except Exception as e:
        logger.exception("Error while fetching aggregated data")
        return ResponseSchema(
            status="error",
            topic=topic,
            data=ErrorData(message="Failed to retrieve data", detail=str(e)).dict(),
        ).dict()

    # 4️⃣ Success — return the aggregated data directly
    logger.info(f"Returning aggregated data for topic={topic}")
    return ResponseSchema(status="success", topic=topic, data=aggregated_data).dict()


# -------------------------
# 🧩 Agent Registration
# -------------------------
hmm_call_prep = Agent(
    name="hmm_call_prep",
    model="gemini-2.0-flash",
    description="Agent that validates input and retrieves patient aggregated data for HMM call prep.",
    instruction=prompt.CALL_PREP_AGENT_PROMPT,
    tools=[hmm_get_data],
)
