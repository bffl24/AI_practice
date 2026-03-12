import logging
import json, random
from typing import Any, Dict, Optional, List

from pydantic import BaseModel, Field
from google.adk.agents import Agent, SequentialAgent
from google.adk.tools.tool_context import ToolContext

from .tools.schema.enums import Flow
from ..llm_config import LlmConfigManager

from . import prompt
from .tools.api_client.orchestrator import PatientOrchestrator
from .tools.aggregator import PatientDataAggregator
from .tools.helpers.helper import ExtractedTopic, topic_extractor
from .tools.helpers.timer_context import TimerContext

logger = logging.getLogger(__name__)


async def hmm_get_data(topic: Any, tool_context: ToolContext) -> Dict[str, Any]:
    extractor_result, flow_status = topic_extractor(topic)
    logger.info(f"extractor_result: {extractor_result}, flow_status: {flow_status}")

    if not extractor_result.is_valid:
        return {"status": "error", "topic": topic}

    try:
        async with PatientOrchestrator() as orchestrator:
            with TimerContext(
                request_id=f"HMM-CALL-PREP-Agent-{random.getrandbits(128)}"
            ):
                aggregator = PatientDataAggregator(orchestrator)
                member_data = await aggregator.get_patient_aggregated_data(
                    subscriber_id=extractor_result.subscriber_id,
                    fep_id=extractor_result.fep_id,
                    member_id=extractor_result.member_id,
                    first_name=extractor_result.first_name,
                    last_name=extractor_result.last_name,
                    date_of_birth=extractor_result.date_of_birth,
                    flow_status=flow_status,
                )

                if member_data:
                    logger.info(f"Member Data: {json.dumps(member_data, indent=2)}")

                return {
                    "status": "success",
                    "data": member_data,
                    "topic": topic,
                }

    except Exception as e:
        logger.exception(
            "Call Prep Agent: Error fetching data from PatientDataAggregator"
        )
        return {
            "status": "error",
            "data": f"Failed to retrieve data: {str(e)}",
            "topic": topic,
        }


# ============================================================
# OUTPUT SCHEMA
# ============================================================

class ContactInformation(BaseModel):
    primary_phone: Optional[str] = None
    alternate_phone: Optional[str] = None
    do_not_call: Optional[bool] = None
    note: Optional[str] = None


class MedicationItem(BaseModel):
    drug_name: Optional[str] = None
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    source: Optional[str] = None


class EncounterItem(BaseModel):
    hospital_name: Optional[str] = None
    admission_date: Optional[str] = None
    discharge_date: Optional[str] = None
    encounter_type: Optional[str] = None


class DiagnosisItem(BaseModel):
    code: Optional[str] = None
    description: Optional[str] = None


class HMMCallPrepOutput(BaseModel):
    member_name: Optional[str] = None
    subscriber_id: Optional[str] = None
    member_id: Optional[str] = None
    birth_date: Optional[str] = None
    age: Optional[int] = None

    disposition_upon_discharge: Optional[str] = None
    pharmacy_status: Optional[str] = None

    contact_information: ContactInformation = Field(default_factory=ContactInformation)

    current_situation_and_diagnosis: Optional[str] = None

    recent_medications_last_120_days: List[MedicationItem] = Field(default_factory=list)
    hospitalizations_last_120_days: List[EncounterItem] = Field(default_factory=list)
    er_visits_last_120_days: List[EncounterItem] = Field(default_factory=list)
    all_diagnoses: List[DiagnosisItem] = Field(default_factory=list)

    data_status: str = "success"
    error_message: Optional[str] = None


# ============================================================
# Agent registration
# ============================================================

try:
    llm_config_manager = LlmConfigManager()

    # Step 1: existing fetch agent
    hmm_call_prep = Agent(
        name="hmm_call_prep",
        model=llm_config_manager.model_name,
        description=(
            "Fetches patient aggregated data from the API service for HMM Call Preparation. "
            "Accepts input as SubscriberID/MemberID or FirstName, LastName and DOB."
        ),
        instruction=prompt.HMM_CALL_PREP_AGENT_PROMPT,
        generate_content_config=llm_config_manager.get_config(),
        tools=[hmm_get_data],
        output_key="raw_hmm_call_prep_result",
    )

    # Step 2: formatter-only agent
    hmm_call_prep_formatter = Agent(
        name="hmm_call_prep_formatter",
        model=llm_config_manager.model_name,
        description="Formats fetched HMM data into the final structured output schema.",
        instruction=prompt.HMM_CALL_PREP_FORMATTER_PROMPT,
        generate_content_config=llm_config_manager.get_config(),
        output_schema=HMMCallPrepOutput,
        output_key="formatted_hmm_call_prep_result",
    )

    # Export this pipeline to the root agent
    hmm_call_prep_pipeline = SequentialAgent(
        name="hmm_call_prep_pipeline",
        description="Runs HMM fetch and then final schema formatter.",
        sub_agents=[hmm_call_prep, hmm_call_prep_formatter],
    )

except RuntimeError as e:
    logger.critical(f"Application cannot start without valid LLM configuration: {e}")
