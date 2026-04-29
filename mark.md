**Here is the aggregated Member data for Subscriber ID [subscriber_id]:**

- **Member Name:** [first_name] [last_name]
- **Member Date of Birth:** [birth_date]
- **Member Age:** [age]
- **Subscriber ID:** [subscriber_id]

**Contact Information:**

[For each contact source in phoneNumbers]

- **[CONTACT_SOURCE_NAME]:**
  - [phone_number_1]
  - [phone_number_2]

[If source exists but has no phone numbers]

- **[CONTACT_SOURCE_NAME]:**
  - No information found.

[If phoneNumbers is completely empty or missing]

- No information found.

[If doNotCall is true]

- **Do Not Call:** Member on Do Not Call List.

**Current Situation and Diagnosis:**

[current_situation_text]

**Current Medications (Last 120 Days):**

**CVS:**

[For each CVS Pharmacy item]

- **[drug_name]:** [rxDirection]

[If no CVS Pharmacy data]

- No information found.

**MHK Self Reporting:**

[For each MHK Pharmacy item]

- **[drug]:** Dosage: [dosage] | Frequency: [frequency] | Route: [route]

[If no MHK Pharmacy data]

- No information found.

**Medical Pharmacy (Last 6 Months):**

[For each Medical Pharmacy / meddrug item]

- **[meddrug_name]:** [available_meddrug_details]

[If no Medical Pharmacy data]

- No information found.

**Most recent Hospitalization:**

**MHK Notes:**

- **Hospitalization:** [mhk_hosp_start_date] - [mhk_hosp_end_date]
- **Provider:** [mhk_hosp_provider]
- **Diagnosis:**
  - [mhk_diagnosis_desc_1]
  - [mhk_diagnosis_desc_2]

[If no MHK hospitalization data]

- **Hospitalization:** No information found.
- **Provider:** No information found.
- **Diagnosis:**
  - No information found.

**Claims:**

- **Hospitalization:** [hosp_start_date] - [hosp_end_date]
  - **Provider:** [hosp_provider]
  - **ICD-10 Primary Diagnosis Code:** [hosp_diagnosis_code]
  - **ICD-10 Primary Diagnosis Code Description:** [hosp_diagnosis_desc]

[If no Claims hospitalization data]

- **Hospitalization:** No information found.
  - **Provider:** No information found.
  - **ICD-10 Primary Diagnosis Code:** No information found.
  - **ICD-10 Primary Diagnosis Code Description:** No information found.

- **ER Visit:** [er_start_date] - [er_end_date]
  - **Provider:** [er_provider]
  - **ICD-10 Primary Diagnosis Code:** [er_diagnosis_code]
  - **ICD-10 Primary Diagnosis Code Description:** [er_diagnosis_desc]

[If no Claims ER Visit data]

- **ER Visit:** No information found.
  - **Provider:** No information found.
  - **ICD-10 Primary Diagnosis Code:** No information found.
  - **ICD-10 Primary Diagnosis Code Description:** No information found.

**Caution:** Please verify this information before use.
