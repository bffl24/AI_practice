import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from google.adk.agents import Agent, SequentialAgent
from google.adk.tools.tool_context import ToolContext

from . import prompt
from .tools.client import HealthcareApiClient
from .tools.aggregator import PatientDataAggregator

logger = logging.getLogger(__name__)


# ============================================================
# FINAL FORMATTER SCHEMA
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
# hmm_get_data remains the smart orchestrator:
# - normal flow
# - FEP member list
# - FEP choice parsing
# - final resolved member data
# ============================================================

async def hmm_get_data(topic: str, tool_context: ToolContext) -> Dict[str, Any]:
    logger.info(f"--- Tool: hmm_get_data called with topic: {topic} ---")

    patient_id = tool_context.state.get("patient_id")
    patient_name = tool_context.state.get("patient_name")

    if not patient_id and not patient_name:
        result = {
            "status": "error",
            "resolution_status": "input_missing",
            "member_selection_required": False,
            "error_message": "Subscriber ID or patient name is missing.",
            "data": {},
        }
        tool_context.state["raw_hmm_call_result"] = result
        return result

    try:
        async with HealthcareApiClient() as client:
            aggregator = PatientDataAggregator(client)

            # IMPORTANT:
            # This method is assumed to already handle:
            # - FEP detection
            # - member list response
            # - parsing of user's FEP_CHOICE reply
            # - final resolved fetch
            all_patient_data = await aggregator.get_all_patient_data(
                patient_id=patient_id,
                patient_name=patient_name,
            )

        # ------------------------------------------------
        # CASE 1: tool/backend says member list needs selection
        # Adjust these keys to your actual payload
        # ------------------------------------------------
        member_list = (
            all_patient_data.get("fep_member_list")
            or all_patient_data.get("member_list")
            or all_patient_data.get("memberSelectionList")
        )

        if member_list:
            member_candidates = []
            for idx, member in enumerate(member_list, start=1):
                member_id = member.get("memberId") or member.get("member_id")
                first_name = member.get("firstName") or member.get("first_name")
                last_name = member.get("lastName") or member.get("last_name")
                birth_date = member.get("birthDate") or member.get("birth_date")

                member_candidates.append(
                    {
                        "serial_number": idx,
                        "member_id": member_id,
                        "first_name": first_name,
                        "last_name": last_name,
                        "birth_date": birth_date,
                        "display_text": (
                            f"{idx}. {first_name} {last_name} - "
                            f"Member ID: {member_id} - DOB: {birth_date}"
                        ),
                    }
                )

            result = {
                "status": "success",
                "resolution_status": "member_selection_required",
                "member_selection_required": True,
                "subscriber_id": patient_id,
                "member_candidates": member_candidates,
                "data": {},
            }
            tool_context.state["raw_hmm_call_result"] = result
            return result

        # ------------------------------------------------
        # CASE 2: resolved member payload
        # ------------------------------------------------
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

        result = {
            "status": "success",
            "resolution_status": "member_resolved",
            "member_selection_required": False,
            "subscriber_id": demographics.get("subscriberId") or patient_id,
            "data": topic_map,
        }
        tool_context.state["raw_hmm_call_result"] = result
        return result

    except Exception as e:
        logger.exception("Error during HMM fetch flow")
        result = {
            "status": "error",
            "resolution_status": "fetch_failed",
            "member_selection_required": False,
            "error_message": f"Failed to retrieve data: {str(e)}",
            "data": {},
        }
        tool_context.state["raw_hmm_call_result"] = result
        return result


# ============================================================
# AGENT 1: FETCH / ORCHESTRATION
# ============================================================

hmm_call_prep = Agent(
    name="hmm_call_prep",
    model="gemini-2.0-flash",
    description="Retrieves HMM data and handles FEP member-selection flow through hmm_get_data.",
    instruction=prompt.CALL_PREP_AGENT_PROMPT,
    tools=[hmm_get_data],
    output_key="raw_hmm_call_result",
)


# ============================================================
# AGENT 2: FORMATTER
# ============================================================

hmm_call_prep_formatter = Agent(
    name="hmm_call_prep_formatter",
    model="gemini-2.0-flash",
    description="Formats only resolved HMM patient data into the final schema.",
    instruction=prompt.CALL_PREP_FORMATTER_PROMPT,
    output_schema=HMMCallPrepOutput,
    output_key="formatted_hmm_call_prep_result",
)


# ============================================================
# PIPELINE
# ============================================================

hmm_call_prep_pipeline = SequentialAgent(
    name="hmm_call_prep_pipeline",
    description="Runs HMM retrieval first, then formats only resolved results.",
    sub_agents=[
        hmm_call_prep,
        hmm_call_prep_formatter,
    ],
)
