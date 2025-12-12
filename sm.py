<OUTPUT_FORMAT>
  <INSTRUCTIONS>
    - Return output inside ONE fenced Markdown code block using ```text
    - Enforce strict vertical layout (one label per line).
    - Never merge multiple fields on the same line.
    - Preserve blank lines and indentation exactly as shown.
    - Do not add commentary, bullets, emojis, or tables.
    - Diagnosis must always be list-view (code and description on separate lines).
  </INSTRUCTIONS>

  <NULL_HANDLING>
    - current_situation_and_diagnosis null → "No current status and diagnosis information found."
    - pharmacy empty → "CVS: No recent medications on record."
    - mhkpharmacy empty → "MHK: Self Reporting: No recent self reported medications on record."
    - ADT phones empty → "ADT: No phone numbers on record."
  </NULL_HANDLING>

  <TEMPLATE>
```text
Here is the aggregated Member data for Subscriber ID &lt;subscriber_id&gt;:

Member Name: &lt;first_name&gt; &lt;last_name&gt;
Member Date of Birth: &lt;birth_date&gt;
Member Age: &lt;age&gt;
Subscriber ID: &lt;subscriber_id&gt;

Contact Information:
ADT:
        &lt;adt_phone_1&gt;
        &lt;adt_phone_2&gt;

Current Situation and Diagnosis:
&lt;current_situation_text&gt;

Current Medications (Last 120 Days):
CVS: &lt;cvs_text&gt;
MHK: Self Reporting: &lt;mhk_text&gt;

Most recent ER Visit and Hospitalization dates:
        Hospitalization: &lt;hosp_start_date&gt; - &lt;hosp_end_date&gt;
        Provider: &lt;hosp_provider&gt;
        Primary Diagnosis Code: &lt;hosp_dx_code&gt; ICD-10
        Primary Diagnosis Code Description: &lt;hosp_dx_desc&gt;

        ER Visit: &lt;er_start_date&gt; - &lt;er_end_date&gt;
        Provider: &lt;er_provider&gt;
        Primary Diagnosis Code: &lt;er_dx_code&gt; ICD-10
        Primary Diagnosis Code Description: &lt;er_dx_desc&gt;

Caution : Please verify this information before use.
</TEMPLATE> </OUTPUT_FORMAT> ```
