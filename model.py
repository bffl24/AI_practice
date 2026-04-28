# ==========================================
# MEDICATION MODELS — FIXED
# ==========================================

class MHKMedicationItem(BaseModel):
    """Matches the MHK pharmacy raw data keys exactly."""
    medication: Optional[str] = None       # ← use "medication", not "drug_name"
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    routeOfAdmin: Optional[str] = None


class CVSMedicationItem(BaseModel):
    """CVS data arrives as raw strings — parse them before populating."""
    drug_name: Optional[str] = None
    rx_direction: Optional[str] = None
    # Remove `source` unless you're adding it manually downstream

    @classmethod
    def from_raw_string(cls, raw: str) -> "CVSMedicationItem":
        """
        Parses: 'TORSEMIDE 20MG TAB, rxDirection: None'
        into structured fields.
        """
        parts = raw.split(", rxDirection:")
        drug = parts[0].strip() if parts else None
        direction = parts[1].strip() if len(parts) > 1 else None
        return cls(
            drug_name=drug,
            rx_direction=None if direction == "None" else direction,
        )


class MedicalPharmacyItem(BaseModel):
    """Meddrug data is a flat string list — one item per entry."""
    meddrug: Optional[str] = None

    @classmethod
    def from_raw_string(cls, raw: str) -> "MedicalPharmacyItem":
        return cls(meddrug=raw.strip())
