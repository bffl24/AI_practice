4. OUTPUT FORMAT RULE:
--- OUTPUT_FORMAT ---

- Do NOT wrap the output in a markdown code block.
- Format the output strictly using standard Markdown rich text.
- Use bolding `**` for all section headers and field labels.
- PRESERVE LINE BREAKS: You MUST use proper Markdown spacing with blank lines between sections so the text does not clump together.
- Do NOT collapse multiple fields into one paragraph.
- Each field must appear on its own line.

- MARKDOWN ONLY RULE:
  - Use standard Markdown only.
  - Do NOT include HTML tags such as `<br>`, `&nbsp;`, `<p>`, `<div>`, or any other HTML formatting.
  - Use standard Markdown line breaks and blank lines only.
  - Use a standard Markdown hyphen and space (`- `) for all bullet points.
  - For nested bullet points, indent with two spaces before `- `.

- CONTACT INFORMATION RENDERING RULE:
  - Dynamically render a contact block for EVERY source found in the `phoneNumbers` JSON data.
  - Format each source name in bold.
  - Example: `- **ADT:**`
  - List EVERY phone number as a nested bullet under its source.
  - If a source has only one phone number, print only that number.
  - If a source is present but empty, print `No information found.` as a bullet under that source.
  - If the `phoneNumbers` data is completely empty, missing, null, or unavailable, print exactly:

    **Contact Information:**

    - No information found.

  - If `doNotCall` is `true`, print:
    `- **Do Not Call:** Member on Do Not Call List.`
  - If `doNotCall` is `false`, missing, null, or unavailable, do not print the Do Not Call line.

- PLACEHOLDER SAFETY RULE:
  - Square-bracket placeholders `[ ]` are template instructions only.
  - Do NOT print raw placeholder text under any circumstance.
  - Do NOT print template control instructions such as `[For each...]`, `[If...]`, `[END REPEAT]`, or similar text.
  - If any placeholder value is missing, null, blank, unavailable, or not found, replace it with exactly:
    `No information found.`
  - Do NOT infer, guess, or create values that are not present in the source JSON.

- INDENTATION & LIST RULE:
  - Use a standard Markdown hyphen and space (`- `) for list items.
  - Do NOT use double hyphens like `--`.
  - Do NOT use bullets such as `•`, `*`, or numbered lists unless explicitly shown in the template.
  - For nested fields under Claims Hospitalization or ER Visit, use two spaces followed by `- `.
  - `MHK Notes:` and `Claims:` are structural sub-headers and MUST be bolded on their own lines.

- DATA PARSING RULE:
  - You must strictly output the data conforming to the template below.
  - Extract the raw data exactly as it appears in the source JSON.
  - Do NOT add clinical interpretation, assumptions, or inferred values.
  - For CVS Pharmacy items, separate and display the drug name and `rxDirection`.
  - For MHK Pharmacy items, map and display the drug, dosage, frequency, and route.
  - For Medical Pharmacy / meddrug items, display all relevant available medication details in a readable Markdown bullet.
  - If a value is missing or an array is empty, output exactly:
    `No information found.`

- ENCOUNTER RENDERING RULE:
  - Keep MHK Notes and Claims encounter data separate.
  - Under MHK Notes, display only the most recent hospitalization data extracted from MHK Notes.
  - Do NOT extract ER visits from MHK Notes.
  - Under Claims, display the most recent Hospitalization and the most recent ER Visit separately.
  - Diagnosis values must be displayed in list format where multiple diagnosis values are present.
  - If diagnosis data is unavailable, print:
    `- No information found.`
  - Do NOT use note dates, claim metadata dates, processing dates, or unrelated timestamps as encounter dates.
  - Use only dates explicitly tied to the hospitalization or ER event.
  - If the patient is currently admitted and no discharge date is present, print:
    `Currently Admitted`
  - If the discharge date is missing and the patient is not clearly currently admitted, print:
    `No information found.`

--- END OUTPUT_FORMAT ---
