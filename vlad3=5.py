# tools/validator.py
"""
Validator for HMM Call-Prep (ADK Web compatible)

Accepts:
  PATH 1 – ID:
     "050028449/00" or "05002844900"
     or conversational text containing those (e.g., "subscriber 050028449/00")
  PATH 2 – Name+DOB:
     "Raja Panda, 04-22-1980"
     or conversational text containing it

Returns tuple: (bool, Optional[dict], Optional[str])
  payload["method"] is "id" or "name_dob"
"""

import re
from typing import Any, Dict, Optional, Tuple
from datetime import datetime, date

IdentityResult = Tuple[bool, Optional[Dict[str, Any]], Optional[str]]

# Relaxed patterns: match IDs or Name+DOB anywhere in the string
_RE_ID_SLASH = re.compile(r'(\d{9})[\/\\](\d{2})')
_RE_ID_11 = re.compile(r'(\d{11})')
_RE_NAME_DOB = re.compile(r'(?P<name>[A-Za-z][A-Za-z\s]+?),\s*(?P<date>[0-9]{1,4}[-/][0-9]{1,2}[-/][0-9]{2,4})')
_DATE_FORMATS = ["%m-%d-%Y", "%m/%d/%Y", "%Y-%m-%d"]


# --------------------- helpers ---------------------
def _safe_str(v: Any) -> str:
    try:
        return str(v).strip()
    except Exception:
        return ""


def _normalize_dob(raw: str) -> Optional[str]:
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
        alt = s.replace("/", "-")
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
    parts = [p for p in _safe_str(fullname).split() if p]
    if len(parts) < 2:
        return None
    return parts[0].lower(), " ".join(parts[1:]).lower()


# --------------------- validator ---------------------
def validate_input(inp: Any) -> IdentityResult:
    """Detect ID or Name+DOB path; normalize and return."""
    # Extract text if dict
    if isinstance(inp, dict):
        for key in ("input", "text", "message", "query", "user_message", "topic"):
            if isinstance(inp.get(key), str) and inp[key].strip():
                return validate_input(inp[key].strip())

        # structured fields fallback
        sub = inp.get("subscriber_id") or inp.get("subscriber")
        mem = inp.get("member_id") or inp.get("member")
        fn = inp.get("first_name") or inp.get("fname")
        ln = inp.get("last_name") or inp.get("lname")
        dob = inp.get("dob") or inp.get("date_of_birth")

        if sub and mem:
            s_sub, s_mem = _safe_str(sub), _safe_str(mem)
            return True, {
                "method": "id",
                "subscriber_id": s_sub,
                "member_id": s_mem,
                "full_id": f"{s_sub}/{s_mem}"
            }, None

        if fn and ln and dob:
            dob_norm = _normalize_dob(dob)
            if not dob_norm:
                return False, None, "Invalid DOB format."
            first, last = _split_name(f"{fn} {ln}")
            return True, {
                "method": "name_dob",
                "first_name": first,
                "last_name": last,
                "display_name": f"{first.title()} {last.title()}",
                "dob": dob_norm
            }, None

        return False, None, "Invalid structured input."

    # If plain string
    if isinstance(inp, str):
        s = inp.strip()

        # -------- ID patterns (search anywhere) --------
        m_id = _RE_ID_SLASH.search(s)
        if m_id:
            return True, {
                "method": "id",
                "subscriber_id": m_id.group(1),
                "member_id": m_id.group(2),
                "full_id": f"{m_id.group(1)}/{m_id.group(2)}",
            }, None

        m11 = _RE_ID_11.search(s)
        if m11:
            fid = m11.group(1)
            return True, {
                "method": "id",
                "subscriber_id": fid[:9],
                "member_id": fid[-2:],
                "full_id": f"{fid[:9]}/{fid[-2:]}",
            }, None

        # -------- Name + DOB (comma required) --------
        conv = _RE_NAME_DOB.search(s)
        if conv:
            name_part = conv.group("name")
            date_part = conv.group("date")
            nm = _split_name(name_part)
            if not nm:
                return False, None, "Name must include first and last."
            dob_norm = _normalize_dob(date_part)
            if not dob_norm:
                return False, None, "DOB invalid or future date."
            first, last = nm
            return True, {
                "method": "name_dob",
                "first_name": first,
                "last_name": last,
                "display_name": f"{first.title()} {last.title()}",
                "dob": dob_norm
            }, None

        return False, None, (
            "Input not recognized. Expected ID like '#########/##' or '###########', "
            "or Name+DOB like 'First Last, MM-DD-YYYY'."
        )

    return False, None, "Unsupported input type. Must be string or dict."
