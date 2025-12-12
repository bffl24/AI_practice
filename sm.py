<OUTPUT_FORMAT>
- Output MUST be inside a single Markdown code block using ```text
- Use one field per line. Never merge labels.
- Preserve line breaks and indentation exactly.
- Diagnosis must always be list-view (code and description on separate lines).

<TEMPLATE>
```text
Here is the aggregated Member data for Subscriber ID <subscriber_id>:

Member Name: <first_name> <last_name>
Member Date of Birth: <birth_date>
Member Age: <age>
Subscriber ID: <subscriber_id>

Contact Information:
ADT:
        <adt_phone_1>
        <adt_phone_2>

Current Situation and Diagnosis:
<current_situation_text>

Current Medications (Last 120 Days):
CVS: <cvs_text>
MHK: Self Reporting: <mhk_text>

Most recent ER Visit and Hospitalization dates:
        Hospitalization: <hosp_start_date> - <hosp_end_date>
        Provider: <hosp_provider>
        Primary Diagnosis Code: <hosp_dx_code> ICD-10
        Primary Diagnosis Code Description: <hosp_dx_desc>

        ER Visit: <er_start_date> - <er_end_date>
        Provider: <er_provider>
        Primary Diagnosis Code: <er_dx_code> ICD-10
        Primary Diagnosis Code Description: <er_dx_desc>

Caution : Please verify this information before use.
</TEMPLATE> </OUTPUT_FORMAT> ```
