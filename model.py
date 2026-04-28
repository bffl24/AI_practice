class HMMCallPrepOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: Literal["HMMCallPrepOutputField"] = "HMMCallPrepOutputField"

    mhkPharmacy: List[MHKMedicationItem] = Field(
        default_factory=list,
        description=(
            "Medications from MHK pharmacy source. "
            "Each item has medication name, dosage, frequency, and routeOfAdmin. "
            "Extract from the mhkPharmacy array in the input data."
        )
    )
    cvsPharmacy: List[CVSMedicationItem] = Field(
        default_factory=list,
        description=(
            "Medications from CVS pharmacy. Input is a flat string like "
            "'TORSEMIDE 20MG TAB, rxDirection: None'. "
            "Parse drug_name as everything before the comma, "
            "rx_direction as the value after 'rxDirection:'. "
            "If rx_direction is the string 'None', set it to null."
        )
    )
    medPharmacy: List[MedicalPharmacyItem] = Field(
        default_factory=list,
        description=(
            "Medical/injection drugs from the meddrug list. "
            "Each string becomes one MedicalPharmacyItem with the full string as meddrug."
        )
    )
