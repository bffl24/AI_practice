<OUTPUT_FORMAT>
  - Output MUST be inside a single Markdown code block using ```text.
  - Use one field per line. Never merge labels.
  - Preserve line breaks and indentation exactly as shown in <TEMPLATE>.
  - Do NOT remove, reorder, rename, or inline any labels from the template.

  - STRICT LINE RULE:
    - NEVER place more than one label on the same line.
    - A label MUST occupy its own line exactly as written in the template.
    - Values MUST appear on the same line as their label ONLY when the template shows it that way.

  - CONTACT INFORMATION RENDERING RULE:
    - Render a contact source block ONLY if that source name is actually available in the data.
    - NEVER print unresolved template variables such as:
      <CONTACT_source_1>
      <CONTACT_source_2>
      <phone_number_1>
      <phone_number_2>
    - If only one contact source exists, print only that one source block.
    - If two contact sources exist, print both source blocks.
    - If a source exists but has only one phone number, print only one phone number line.
    - If a source exists but no phone number is available, print:
      No information found.
    - If no contact source data exists at all, print exactly:
      Contact Information:
        No information found.

  - PLACEHOLDER SAFETY RULE:
    - Angle-bracket placeholders are template instructions only.
    - They MUST NEVER appear in the final user-facing output.
    - If any placeholder value is unavailable, replace it with "No information found."
    - Do NOT print raw placeholder text under any circumstance.

  - SECTION HEADER RULE:
    - "MHK Notes:", "ADT:", and "Claims:" are structural headers.
    - They MUST always appear on their own line.
    - They MUST NEVER share a line with Hospitalization, ER Visit, Provider, or Diagnosis content.

  - BLOCK SEPARATION RULE:
    - Each of the following blocks MUST be visually separated by line breaks:
      • MHK Notes → Hospitalization
      • ADT → Hospitalization
      • ADT → ER Visit
      • Claims Payment API → Hospitalization
      • Claims Payment API → ER Visit
    - For Claims Payment API, ICD-10 Code and Description MUST remain on separate lines.

  - Markdown List:
    - Use a hyphen and space (`- `) for the first line.
    - For any text that wraps to a second line, you MUST start that line with 4 leading spaces.
    - The goal is a "Hanging Indent" where text aligns under text, not the bullet.

  - INDENTATION RULE:
    - Preserve indentation exactly as shown in <TEMPLATE>.
    - Do NOT normalize, collapse, or rewrite whitespace.
    - Do NOT convert indentation into inline text.

  - ERROR PREVENTION:
    - Do NOT compress multiple fields into one paragraph.
    - Do NOT rewrite the template into prose.
    - For Contact Information, DO NOT print unused source blocks.
    - If data is missing, print "No information found." instead of raw template placeholders.

  <TEMPLATE>
    Here is the aggregated Member data for Subscriber ID <subscriber_id>:

    Member Name: <first_name> <last_name>
    Member Date of Birth: <birth_date>
    Member Age: <age>
    Subscriber ID: <subscriber_id>

    Contact Information:

      <CONTACT_source_1>:
        <phone_number_1>
        <phone_number_2>

      <CONTACT_source_2>:
        <phone_number_1>
        <phone_number_2>

    Current Situation and Diagnosis:
    <current_situation_text>

    Current Medications (Last 120 Days):

      CVS:
        - <cvs_pharmacy_list>

      MHK Self Reporting:
        - <mhk_medication_list>

      Medical Pharmacy (Last 6 Months):
        - <medical_pharmacy_list>

    Most recent Hospitalization:

      MHK Notes:
        Hospitalization: <mhk_hosp_start_date - mhk_hosp_end_date or No information found>
        Provider: <mhk_hosp_provider>
        Diagnosis:
          - <mhk_hosp_diagnosis_list>

      ADT:
        Hospitalization: <adt_hosp_start_date - adt_hosp_end_date or No information found>
        Provider: <adt_hosp_provider>
        Diagnosis:
          - <adt_hosp_diagnosis_list>

        ER Visit: <adt_er_start_date - adt_er_end_date or No information found>
        Provider: <adt_er_provider>
        Diagnosis:
          - <adt_er_diagnosis_list>

    Claims:

      Hospitalization: <hosp_start_date - hosp_end_date or No information found>
      Provider: <hosp_provider>
      Primary Diagnosis Code: <hosp_diagnosis_code>
      Primary Diagnosis Code Description: <hosp_diagnosis_desc>

      ER Visit: <er_start_date - er_end_date or No information found>
      Provider: <er_provider>
      Primary Diagnosis Code: <er_diagnosis_code>
      Primary Diagnosis Code Description: <er_diagnosis_desc>

    Caution: Please verify this information before use.
  </TEMPLATE>
</OUTPUT_FORMAT>
