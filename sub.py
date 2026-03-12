import logging
import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from google.adk.agents import Agent, SequentialAgent
from google.adk.tools.tool_context import ToolContext

from . import prompt
from .tools.client import HealthcareApiClient
from .tools.aggregator import PatientDataAggregator

logger = logging.getLogger(__name__)


# ============================================================
# OUTPUT SCHEMA
# ============================================================

class DiagnosisItem(BaseModel):
    icd10_primary_diagnosis_code: Optional[str] = None
    icd10_primary_diagnosis_code_description: Optional[str] = None


class ClaimEncounter(BaseModel):
    service_type: Optional[str] = None
    admission_date: Optional[str] = None
    discharge_date: Optional[str] = None
    provider_name: Optional[str] = None
    primary_diagnoses: List[DiagnosisItem] = Field(default_factory=list)


class MHKEncounter(BaseModel):
    encounter_type: Optional[str] = None
    admission_date: Optional[str] = None
    discharge_date: Optional[str] = None
    provider_name: Optional[str] = None
    diagnosis_text: List[str] = Field(default_factory=list)
    supporting_note_date: Optional[str] = None
    supporting_note_text: Optional[str] = None


class MostRecentHospitalizationDates(BaseModel):
    mhk_notes_hospitalization: Optional[MHKEncounter] = None
    claims_hospitalization: Optional[ClaimEncounter] = None
    claims_er_visit: Optional[ClaimEncounter] = None


class ContactInformation(BaseModel):
    primary_phone: Optional[str] = None
    alternate_phone: Optional[str] = None
    do_not_call: Optional[bool] = None
    note: Optional[str] = None


class MedicationItem(BaseModel):
    drug_name: Optional[str] = None
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    availability: Optional[str] = None
    source: Optional[str] = None


class HMMCallPrepOutput(BaseModel):
    member_name: Optional[str] = None
    subscriber_id: Optional[str] = None
    birth_date: Optional[str] = None
    age: Optional[int] = None

    disposition_upon_discharge: Optional[str] = None
    pharmacy_status: Optional[str] = None

    contact_information: ContactInformation = Field(default_factory=ContactInformation)

    current_situation_and_diagnosis: List[str] = Field(default_factory=list)
    recent_medications_last_120_days: List[MedicationItem] = Field(default_factory=list)

    most_recent_hospitalization_dates: MostRecentHospitalizationDates = Field(
        default_factory=MostRecentHospitalizationDates
    )

    data_status: str = "success"
    error_message: Optional[str] = None


# ============================================================
# TOOL
# ============================================================

async def hmm_get_data(topic: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Gather data for HMM call preparation using API services.
    Fetches demographics, medications, visits, status, and MHK notes context.
    """
    logger.info(f"--- Tool: hmm_get_data called with topic: {topic} ---")

    patient_id = tool_context.state.get("patient_id", "PAT001")
    patient_name = tool_context.state.get("patient_name", "John Smith")

    logger.info(f"patient_id: {patient_id}")
    logger.info(f"patient_name: {patient_name}")
    logger.info(f"tool_context.state: {tool_context.state}")

    if not patient_id and not patient_name:
        return {
            "status": "error",
            "error_message": "Subscriber ID or patient name is missing.",
            "topic": topic,
            "data": {}
        }

    try:
        async with HealthcareApiClient() as client:
            aggregator = PatientDataAggregator(client)
            all_patient_data = await aggregator.get_all_patient_data(
                patient_id=patient_id,
                patient_name=patient_name,
            )
    except Exception as e:
        logger.exception("Error fetching data from PatientDataAggregator")
        return {
            "status": "error",
            "error_message": f"Failed to retrieve data: {str(e)}",
            "topic": topic,
            "data": {}
        }

    demographics = all_patient_data.get("demographics", {})
    medications = all_patient_data.get("medications", {})
    visits = all_patient_data.get("visits", {})
    status = all_patient_data.get("status", {})
    mhk_notes = all_patient_data.get("current_situation_and_diagnosis", [])

    topic_map = {
        "member": demographics,
        "medications": medications,
        "encounters": {
            "claims": {
                "hospitalization": visits.get("hospitalization"),
                "emergency": visits.get("emergency"),
            },
            "mhk_notes": mhk_notes,
        },
        "status": status,
    }

    logger.info(f"Patient Data: {json.dumps(topic_map, indent=2, default=str)}")

    return {
        "status": "success",
        "topic": topic,
        "data": topic_map
    }


# ============================================================
# FETCH AGENT
# ============================================================

hmm_call_prep = Agent(
    name="hmm_call_prep",
    model="gemini-2.0-flash",
    description="Fetches raw HMM data using hmm_get_data.",
    instruction=prompt.CALL_PREP_AGENT_PROMPT,
    tools=[hmm_get_data],
    output_key="raw_hmm_call_prep_result",
)


# ============================================================
# FORMATTER AGENT
# ============================================================

hmm_call_prep_formatter = Agent(
    name="hmm_call_prep_formatter",
    model="gemini-2.0-flash",
    description="Formats HMM call prep data into the strict schema.",
    instruction=prompt.CALL_PREP_FORMATTER_PROMPT,
    output_schema=HMMCallPrepOutput,
    output_key="formatted_hmm_call_prep_result",
)


# ============================================================
# PIPELINE
# ============================================================

hmm_call_prep_pipeline = SequentialAgent(
    name="hmm_call_prep_pipeline",
    description="Fetches HMM data and formats the final structured output.",
    sub_agents=[
        hmm_call_prep,
        hmm_call_prep_formatter,
    ],
)
