# tools/validator.py
"""
Validator for two mutually exclusive input paths for HMM call-prep.

Path A (ID): "050028449/00"  or "05002844900"
Path B (Name+DOB): "First Last, MM-DD-YYYY" (comma required)
"""

import re
from typing import Any, Dict, Optional, Tuple
from datetime import datetime, date

IdentityResult = Tuple[bool, Optional[Dict[str, Any]], Optional[str]]

# Patterns
_RE_ID_SLASH = re.compile(r'^\s*(\d{9})[\/\\](\d{2})\s*$')
_RE_ID_11 = re.compile(r'^\s*(\d{11})\s*$')
_RE_NAME_DOB = re.compile(r'^\s*(?P<name>.+?)\s*,\s*(?P<date>.+?)\s*$')
_DATE_FORMATS = ["%m-%d-%Y", "%m/%d/%Y", "%Y-%m-%d"]


def _safe_str(v: Any) -> str:
    try:
        return str(v).strip()
    except Exception:
        return ""


def _normalize_dob(raw: str) -> Optional[str]:
    """Normalize DOB to MM-DD-YYYY if valid."""
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
        alt = s.replace('/', '-').strip()
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
    """Return (first_lower, last_lower) if valid."""
    s = _safe_str(fullname)
    parts = [p for p in s.split() if p]
    if len(parts) < 2:
        return None
    return parts[0].lower(), " ".join(parts[1:]).lower()


def validate_input(inp: Any) -> IdentityResult:
    """
    Validate user input and return:
      (True, {"method": "id" or "name_dob", ...}, None)
    """
    # Dict-style input (structured)
    if isinstance(inp, dict):
        # Check for raw text fields
        text = None
        for k in ("text", "query", "message", "input", "user_message", "topic"):
            if isinstance(inp.get(k), str):
                text = inp[k].strip()
                break
        if text:
            return validate_input(text)

        # Check for structured fields
        sub = inp.get("subscriber_id") or inp.get("subscriber")
        mem = inp.get("member_id") or inp.get("member")
        fn = inp.get("first_name") or inp.get("fname")
        ln = inp.get("last_name") or inp.get("lname")
        dob = inp.get("dob") or inp.get("date_of_birth")

        # ID route
        if sub and mem:
            sub_s = _safe_str(sub)
            mem_s = _safe_str(mem)
            if not re.fullmatch(r"\d{9}", sub_s):
                return False, None, "subscriber_id must be 9 digits"
            if not re.fullmatch(r"\d{2}", mem_s):
                return False, None, "member_id must be 2 digits"
            return True, {
                "method": "id",
                "subscriber_id": sub_s,
                "member_id": mem_s,
                "full_id": f"{sub_s}/{mem_s}",
            }, None

        # Name+DOB route
        if fn and ln and dob:
            dob_norm = _normalize_dob(dob)
            if not dob_norm:
                return False, None, "Invalid DOB format or future date"
            first, last = _split_name(f"{fn} {ln}")
            return True, {
                "method": "name_dob",
                "first_name": first,
                "last_name": last,
                "display_name": f"{first.title()} {last.title()}",
                "dob": dob_norm,
            }, None

        return False, None, "Invalid dict input — expected ID or Name+DOB"

    # String-style input (unstructured)
    if isinstance(inp, str):
        s = inp.strip()

        # Check ID patterns
        m_id = _RE_ID_SLASH.match(s)
        if m_id:
            return True, {
                "method": "id",
                "subscriber_id": m_id.group(1),
                "member_id": m_id.group(2),
                "full_id": f"{m_id.group(1)}/{m_id.group(2)}",
            }, None

        m11 = _RE_ID_11.match(s)
        if m11:
            fid = m11.group(1)
            return True, {
                "method": "id",
                "subscriber_id": fid[:9],
                "member_id": fid[-2:],
                "full_id": f"{fid[:9]}/{fid[-2:]}",
            }, None

        # Check Name+DOB
        conv = _RE_NAME_DOB.match(s)
        if conv:
            name_part = conv.group("name")
            date_part = conv.group("date")
            nm = _split_name(name_part)
            if not nm:
                return False, None, "Name must include first and last"
            dob_norm = _normalize_dob(date_part)
            if not dob_norm:
                return False, None, "Invalid DOB format"
            first, last = nm
            return True, {
                "method": "name_dob",
                "first_name": first,
                "last_name": last,
                "display_name": f"{first.title()} {last.title()}",
                "dob": dob_norm,
            }, None

        return False, None, "Unrecognized input format"

    return False, None, "Unsupported input type"
