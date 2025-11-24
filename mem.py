    <MEMBER_NOTES_SUMMARY>
      - Always print the header exactly as:
        Member Notes Summary:

      - Use the "notes" array from medical_visits.

      - For each note, generate a single concise paragraph following these rules:

        1. Identify and summarize the member’s most recent significant medical event.
           Examples:
             - Hospital admission
             - New diagnosis
             - ER presentation
             - CT/MRI procedure
             - Rehab/SNF stay
             - Discharge event

        2. Extract the following if available:
             - Current Situation/Status (e.g., "Presented with chest pain", "Inpatient at...", "Undergoing CT scan")
             - Primary diagnosis or medical reason
             - Facility / Provider / Location (e.g., hospital, rehab, SNF)
             - Admission and discharge dates
             - Next Review Date (NRD) or follow-up appointment
             - Discharge status (e.g., home, SNF, pending)

        3. Strictly ignore ALL administrative and non-clinical content:
             - RFC text, call logs, outreach attempts
             - Authorization/billing details
             - System timestamps
             - Case management routing info
             - Abbreviations that do not relate to clinical status

        4. Your summary must be a single, objective, medical paragraph of 2–5 sentences.

      - If notes exist but contain no clinically meaningful information, print:
        No clinically relevant notes available.

      - If no notes exist, print:
        No member notes on record.
    </MEMBER_NOTES_SUMMARY>
