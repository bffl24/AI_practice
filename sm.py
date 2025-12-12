<OUTPUT_FORMAT>
INSTRUCTION:
- Output MUST match the TEMPLATE structure exactly.
- Use STRICT VERTICAL LIST formatting (one field per line).
- NEVER combine multiple labeled fields on one line.
- Use EXACT blank lines (double newlines) between major sections, exactly as shown.
- Do NOT add extra headers, emojis, tables, or commentary.
- Do NOT reorder sections.

GENERAL RULES:
- If a value is missing/null/empty, print the label and the exact "not found" message specified in the TEMPLATE.
- Keep labels EXACT (capitalization and punctuation).
- Keep spacing EXACT:
  - There is ONE blank line between section blocks (double newline).
  - Under "Contact Information:", print the source line (e.g., "ADT:") and then each phone on its own line with the exact indentation shown.
- Phone formatting:
  - Use the strings as already present in JSON (do NOT reformat numbers).
  - If multiple phones exist, print each on its own line.
- Diagnoses formatting:
  - ALWAYS print Primary Diagnosis as a LIST VIEW (each item on its own line).
  - Even if there is only one diagnosis, it must still appear as list lines (not a paragraph).

SOURCE MAPPING (from loader.json):
- subscriber_id = demographics.subscriberId
- first_name = demographics.firstName
- last_name = demographics.lastName
- birth_date = demographics.birthDate
- age = demographics.age
- Contact phones:
  - ADT phones = demographics.phoneNumbers[0].adt (array)
- Current Situation and Diagnosis:
  - current_situation_and_diagnosis:
    - If null/empty => "No current status and diagnosis information found."
- Medications (Last 120 Days):
  - CVS meds = medical_visits.pharmacy (array)
  - MHK self-report meds = medical_visits.mhkpharmacy (array)
  - If empty => print exactly:
    - "CVS: No recent medications on record."
    - "MHK: Self Reporting: No recent self reported medications on record."
- Most recent visits:
  - Hospitalization = medical_visits.hospitalization
  - ER visit = medical_visits.emergency
  - If an encounter object is missing/null => print that block with "No recent <type> visits on record."

DIAGNOSIS LIST VIEW REQUIREMENT (CRITICAL):
- For BOTH Hospitalization and ER Visit:
  - Print diagnoses as list lines, each on its own line, like:
    Primary Diagnosis Code: <code> ICD-10
    Primary Diagnosis Code Description: <description>
  - If multiple diagnoses exist, repeat those two lines for each diagnosis (still one line per item; no paragraphs).

<TEMPLATE>
Here is the aggregated Member data for Subscriber ID <subscriber_id>:

**Member Name**: <first_name> <last_name>
**Member Date of Birth**: <birth_date>
**Member Age**: <age>
**Subscriber ID**: <subscriber_id>

**Contact Information:**
ADT:
        <phone_1>
        <phone_2>

**Current Situation and Diagnosis:**
<current_situation_or_not_found>

**Current Medications (Last 120 Days):**
CVS: <cvs_meds_or_no_records>
MHK: Self Reporting: <mhk_meds_or_no_records>

**Most recent ER Visit and Hospitalization dates:**
        **Hospitalization:** <hosp_start_date> - <hosp_end_date>
        **Provider:** <hosp_provider>
        Primary Diagnosis Code: <hosp_dx_code_1> ICD-10
        Primary Diagnosis Code Description: <hosp_dx_desc_1>

        **ER Visit:** <er_start_date> - <er_end_date>
        **Provider:** <er_provider>
        Primary Diagnosis Code: <er_dx_code_1> ICD-10
        Primary Diagnosis Code Description: <er_dx_desc_1>

Caution : Please verify this information before use.
</TEMPLATE>
</OUTPUT_FORMAT>
