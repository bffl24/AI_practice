# tools/validator.py
"""
Validator for HMM Call-Prep Agent.

Supports exactly two mutually-exclusive input formats:
-------------------------------------------------------
PATH A – ID path:
  • "050028449/00"  (9 digits '/' 2 digits)
  • "05002844900"   (11 digits -> split 9 + 2)

PATH B – Name + DOB path (comma required):
  • "Raja Panda, 04-22-1980"
  • accepts MM-DD-YYYY, MM/DD/YYYY, or YYYY-MM-DD
  • normalizes DOB to MM-DD-YYYY

Returns:
  (valid: bool, payload: Optional[dict], error_message: Optional[str])

payload includes a "method" key with either:
  method = "id"  or  method = "name_dob"
"""

import re
from typing import Any, Dict, Optional, Tuple
from datetime import datetime, date

# ---------------------------------------------------------------------
# Type alias for clarity
IdentityResult = Tuple[bool, Optional[Dict[str, Any]], Optional[str]]
# ---------------------------------------------------------------------

# Regex patterns
_RE_ID_SLASH = re.compile(r'^\s*(\d{9})[\/\\](\d{2})\s*$')
_RE_ID_11 = re.compile(r'^\s*(\d{11})\s*$')
_RE_NAME_DOB = re.compile(r'^\s*(?P<name>.+?)\s*,\s*(?P<date>.+?)\s*$')
_DATE_FORMATS = ["%m-%d-%Y", "%m/%d/%Y", "%Y-%m-%d"]


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def _safe_str(v: Any) -> str:
    try:
        return str(v).strip()
    except Exception:
        return ""


def _normalize_dob(raw: str) -> Optional[str]:
    """Normalize DOB to MM-DD-YYYY if valid, otherwise None."""
    s = _safe_str(raw)
    if not s:
        return None

    parsed = None
    for fmt in _DATE_FORMATS:
        try:
            parsed = datetime.strptime(s, fmt).date()
            break
        except Exception:
            continue
    if not parsed:
        alt = s.replace("/", "-").strip()
        for fmt in _DATE_FORMATS:
            try:
                parsed = datetime.strptime(alt, fmt).date()
                break
            except Exception:
                continue

    if not parsed or parsed > date.today():
        return None
    return parsed.strftime("%m-%d-%Y")


def _split_name(fullname: str) -> Optional[tuple]:
    """Return (first_lower, last_lower) if valid name."""
    parts = [p for p in _safe_str(fullname).split() if p]
    if len(parts) < 2:
        return None
    first = parts[0].lower()
    last = " ".join(parts[1:]).lower()
    return first, last


# ---------------------------------------------------------------------
# Main validator
# ---------------------------------------------------------------------
def validate_input(inp: Any) -> IdentityResult:
    """
    Validate the given input (string or dict).

    Returns:
      (True, payload_dict, None)     -> when valid
      (False, None, error_message)   -> when invalid
    """
    # -----------------------------------------------------------------
    # If dict-style input (structured from agent state)
    # -----------------------------------------------------------------
    if isinstance(inp, dict):
        # 1) Try to extract raw text if present
        for key in ("text", "query", "message", "input", "user_message", "topic"):
            if isinstance(inp.get(key), str) and inp[key].strip():
                return validate_input(inp[key].strip())

        # 2) Structured fields
        sub = inp.get("subscriber_id") or inp.get("subscriber")
        mem = inp.get("member_id") or inp.get("member")
        fn = inp.get("first_name") or inp.get("fname")
        ln = inp.get("last_name") or inp.get("lname")
        dob = inp.get("dob") or inp.get("date_of_birth")

        # ID path
        if sub and mem:
            sub_s, mem_s = _safe_str(sub), _safe_str(mem)
            if not re.fullmatch(r"\d{9}", sub_s):
                return False, None, "subscriber_id must be exactly 9 digits."
            if not re.fullmatch(r"\d{2}", mem_s):
                return False, None, "member_id must be exactly 2 digits."
            return True, {
                "method": "id",
                "subscriber_id": sub_s,
                "member_id": mem_s,
                "full_id": f"{sub_s}/{mem_s}",
            }, None

        # Name + DOB path
        if fn and ln and dob:
            dob_norm = _normalize_dob(dob)
            if not dob_norm:
                return False, None, "DOB unparseable or in the future."
            nm = _split_name(f"{fn} {ln}")
            if not nm:
                return False, None, "Name must include first and last."
            first, last = nm
            return True, {
                "method": "name_dob",
                "first_name": first,
                "last_name": last,
                "display_name": f"{first.title()} {last.title()}",
                "dob": dob_norm,
            }, None

        return False, None, "Invalid dict input. Provide ID or Name+DOB."

    # -----------------------------------------------------------------
    # If string input (from conversational message)
    # -----------------------------------------------------------------
    if isinstance(inp, str):
        s = inp.strip()

        # --- Path A: ID with slash ---
        m_id = _RE_ID_SLASH.fullmatch(s)
        if m_id:
            return True, {
                "method": "id",
                "subscriber_id": m_id.group(1),
                "member_id": m_id.group(2),
                "full_id": f"{m_id.group(1)}/{m_id.group(2)}",
            }, None

        # --- Path A: 11-digit ID ---
        m11 = _RE_ID_11.fullmatch(s)
        if m11:
            fid = m11.group(1)
            return True, {
                "method": "id",
                "subscriber_id": fid[:9],
                "member_id": fid[-2:],
                "full_id": f"{fid[:9]}/{fid[-2:]}",
            }, None

        # --- Path B: Name + DOB (comma required) ---
        conv = _RE_NAME_DOB.match(s)
        if conv:
            name_part, date_part = conv.group("name"), conv.group("date")
            nm = _split_name(name_part)
            if not nm:
                return False, None, "Name must include first and last."
            dob_norm = _normalize_dob(date_part)
            if not dob_norm:
                return False, None, "DOB unparseable or in the future."
            first, last = nm
            return True, {
                "method": "name_dob",
                "first_name": first,
                "last_name": last,
                "display_name": f"{first.title()} {last.title()}",
                "dob": dob_norm,
            }, None

        # --- Unrecognized format ---
        return False, None, (
            "Input not recognized. Allowed formats:\n"
            "- '#########/##' or '###########' for ID path\n"
            "- 'First Last, MM-DD-YYYY' for Name+DOB path"
        )

    # -----------------------------------------------------------------
    # Unsupported type
    # -----------------------------------------------------------------
    return False, None, "Unsupported input type. Provide a string or dict."
