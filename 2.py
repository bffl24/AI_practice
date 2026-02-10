<OUTPUT_FORMAT>
  - Output MUST be inside a single Markdown code block using ```text.
  - Use one field per line. Never merge labels.
  - Preserve line breaks and indentation exactly as shown in <TEMPLATE>.
  - Do NOT remove, reorder, rename, or inline any labels from the template.

  - STRICT LINE RULE:
    - NEVER place more than one label on the same line.
    - A label MUST occupy its own line exactly as written in the template.
    - Values MUST appear on the same line as their label ONLY when the template shows it that way.

  - SECTION HEADER RULE:
    - "MHK Notes:" and "Claims Payment API:" are structural headers.
    - They MUST always appear on their own line.
    - They MUST NEVER share a line with Hospitalization, ER Visit, Provider, or Diagnosis content.

  - BLOCK SEPARATION RULE:
    - Each of the following blocks MUST be visually separated by line breaks:
      • MHK Notes → Hospitalization
      • MHK Notes → ER Visit
      • Claims Payment API → Hospitalization
      • Claims Payment API → ER Visit

  - DIAGNOSIS FORMATTING (STRICT):
    - Diagnosis MUST always be rendered as a vertical list.
    - Each diagnosis item MUST be on its own line.
    - Comma-separated diagnoses on a single line are FORBIDDEN.
    - For Claims Payment API, ICD-10 Code and Description MUST remain on separate lines.

  - INDENTATION RULE:
    - Preserve indentation exactly as shown in <TEMPLATE>.
    - Do NOT normalize, collapse, or rewrite whitespace.
    - Do NOT convert indentation into inline text.

  - ERROR PREVENTION:
    - Do NOT compress multiple fields into one paragraph.
    - Do NOT rewrite the template into prose.
    - If data is missing, print the placeholder text, but DO NOT remove the line.

  <TEMPLATE>
  ```text
  Here is the aggregated Member data for Subscriber ID <subscriber_id>:

  Member Name: <first_name> <last_name>
  Member Date of Birth: <birth_date>
  Member Age: <age>
  Subscriber ID: <subscriber_id>

  Contact Information:
    <CONTACT_source:
      <phone_1>
      <phone_2>

  Current Situation and Diagnosis:
  <current_situation_text>

  Current Medications (Last 120 Days):
    CVS: <cvs_text>
    MHK: Self Reporting: <mhk_text>

  Most recent ER Visit and Hospitalization dates:

    MHK Notes:
      Hospitalization: <mhk_hosp_start_date> - <mhk_hosp_end_date>
      Provider: <mhk_hosp_provider>
      Diagnosis:
        <mhk_hosp_dx_1>
        <mhk_hosp_dx_2>

      ER Visit: <mhk_er_start_date> - <mhk_er_end_date>
      Provider: <mhk_er_provider>
      Diagnosis:
        <mhk_er_dx_1>
        <mhk_er_dx_2>

    Claims Payment API:
      Hospitalization: <hosp_start_date> - <hosp_end_date>
      Provider: <hosp_provider>
      Primary Diagnosis Code: <hosp_dx_code>
      Primary Diagnosis Code Description: <hosp_dx_desc>

      ER Visit: <er_start_date> - <er_end_date>
      Provider: <er_provider>
      Primary Diagnosis Code: <er_dx_code>
      Primary Diagnosis Code Description: <er_dx_desc>

  Caution : Please verify this information before use.
  </TEMPLATE>
</OUTPUT_FORMAT>
