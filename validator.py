# tools/validator.py
"""
Validator for HMM call-prep input.

Two allowed, mutually-exclusive input formats only:

FORMAT 1 - ID path:
  - "050028449/00"  -> 9 digits, slash, 2 digits
  - "05002844900"   -> 11 digits (will be split into 9 + 2)
Returns:
  {"method":"id", "subscriber_id":"...", "member_id":"..", "full_id":".../.."}

FORMAT 2 - Name + DOB path (comma required):
  - "Raja Panda, 04-22-1980"
  - "Raja Panda, 04/22/1980"
  - "Raja Panda, 1980-04-22"
  -> DOB parsed permissively and normalized to MM-DD-YYYY
Returns:
  {"method":"name_dob", "first_name":"raja", "last_name":"panda",
   "display_name":"Raja Panda", "dob":"MM-DD-YYYY"}

The validator accepts either a raw string or a dict-like input.
Returns tuple: (valid: bool, payload: Optional[dict], error: Optional[str])
"""

import re
from typing import Any, Dict, Optional, Tuple
from datetime import datetime, date

IdentityResult = Tuple[bool, Optional[Dict[str, Any]], Optional[str]]

# Regex patterns
_RE_ID_SLASH = re.compile(r'^\s*(\d{9})[\/\\](\d{2})\s*$')  # "050028449/00"
_RE_ID_11 = re.compile(r'^\s*(\d{11})\s*$')                # "05002844900"
_RE_CONVERSATIONAL = re.compile(r'^\s*(?P<name>.+?)\s*,\s*(?P<date>.+?)\s*$')

# Permissive date formats to try (order matters)
_DATE_FORMATS = ["%m-%d-%Y", "%m/%d/%Y", "%Y-%m-%d"]

def _safe_str(v: Any) -> str:
    try:
        return str(v).strip()
    except Exception:
        return ""

def _parse_normalize_dob(raw: str) -> Optional[str]:
    """
    Parse raw date string into a date and return normalized "MM-DD-YYYY".
    Returns None if unparseable or date is in the future.
    """
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

    # Try a last-resort attempt replacing slashes/hyphens (very permissive)
    if not parsed:
        alt = s.replace('/', '-').strip()
        for fmt in _DATE_FORMATS:
            try:
                parsed = datetime.strptime(alt, fmt).date()
                break
            except Exception:
                continue

    if not parsed:
        return None
    if parsed > date.today():
        return None
    return parsed.strftime("%m-%d-%Y")

def _split_name(fullname: str) -> Optional[tuple]:
    """
    Split a full name into first and last. Requires at least two parts.
    Returns (first_lower, last_lower) or None.
    """
    s = _safe_str(fullname)
    parts = [p for p in s.split() if p]
    if len(parts) < 2:
        return None
    first = parts[0].lower()
    last = " ".join(parts[1:]).lower()
    return first, last

def validate_input(inp: Any) -> IdentityResult:
    """
    Validate and extract identity information from `inp` (str or dict).
    Returns (True, payload, None) on success; (False, None, error_message) on failure.
    """

    # If dict-like input: check structured fields first
    if isinstance(inp, dict):
        # 1) Explicit ID fields (subscriber + suffix)
        subscriber = inp.get("subscriber_id") or inp.get("subscriberId") or inp.get("subscriber")
        suffix = inp.get("suffix") or inp.get("member_suffix") or inp.get("suffix_id")
        member = inp.get("member_id") or inp.get("memberId") or inp.get("member")

        if subscriber and suffix:
            sub_s = _safe_str(subscriber)
            suf_s = _safe_str(suffix)
            if not re.fullmatch(r'\d{9}', sub_s):
                return False, None, "subscriber_id must be exactly 9 digits."
            if not re.fullmatch(r'\d{2}', suf_s):
                return False, None, "suffix (member_id) must be exactly 2 digits."
            return True, {
                "method": "id",
                "subscriber_id": sub_s,
                "member_id": suf_s,
                "full_id": f"{sub_s}/{suf_s}"
            }, None

        if member:
            m = _safe_str(member)
            mslash = _RE_ID_SLASH.fullmatch(m)
            if mslash:
                return True, {
                    "method": "id",
                    "subscriber_id": mslash.group(1),
                    "member_id": mslash.group(2),
                    "full_id": f"{mslash.group(1)}/{mslash.group(2)}"
                }, None
            m11 = _RE_ID_11.fullmatch(m)
            if m11:
                fid = m11.group(1)
                return True, {
                    "method": "id",
                    "subscriber_id": fid[:9],
                    "member_id": fid[-2:],
                    "full_id": f"{fid[:9]}/{fid[-2:]}"
                }, None
            return False, None, "member_id must be '9digits/2digits' or an 11-digit number."

        # 2) Structured name + dob
        fn = inp.get("first_name") or inp.get("firstName") or inp.get("fname")
        ln = inp.get("last_name") or inp.get("lastName") or inp.get("lname")
        dob = inp.get("dob") or inp.get("date_of_birth") or inp.get("birthdate")
        if fn or ln or dob:
            if not (fn and ln and dob):
                return False, None, "Name+DOB path requires first_name, last_name, and dob."
            norm = _parse_normalize_dob(dob)
            if not norm:
                return False, None, "DOB unparseable or in the future. Expected MM-DD-YYYY (or MM/DD/YYYY or YYYY-MM-DD)."
            nm = _split_name(f"{fn} {ln}")
            if not nm:
                return False, None, "Name must include at least first and last name."
            first, last = nm
            display = f"{first.title()} {last.title()}"
            return True, {
                "method": "name_dob",
                "first_name": first,
                "last_name": last,
                "display_name": display,
                "dob": norm
            }, None

        # 3) If dict contains raw text field, fall back to parsing the text
        text = inp.get("text") or inp.get("query") or inp.get("message")
        if isinstance(text, str):
            return validate_input(text)

        return False, None, "Dict input missing required fields. Provide member/subscriber OR first_name+last_name+dob OR a raw text message."

    # If a raw string is provided, parse conversational formats
    if isinstance(inp, str):
        s = inp.strip()

        # ID with slash anywhere
        m_id = _RE_ID_SLASH.search(s)
        if m_id:
            sub = m_id.group(1)
            mem = m_id.group(2)
            return True, {"method": "id", "subscriber_id": sub, "member_id": mem, "full_id": f"{sub}/{mem}"}, None

        # 11-digit anywhere
        m11 = _RE_ID_11.search(s)
        if m11:
            fid = m11.group(1)
            return True, {"method": "id", "subscriber_id": fid[:9], "member_id": fid[-2:], "full_id": f"{fid[:9]}/{fid[-2:]}"}, None

        # Conversational "Name, Date" (comma required)
        conv = _RE_CONVERSATIONAL.match(s)
        if conv:
            name_part = conv.group("name")
            date_part = conv.group("date")
            nm = _split_name(name_part)
            if not nm:
                return False, None, "Name must include at least first and last name (e.g., 'Raja Panda, 04-22-1980')."
            dob_norm = _parse_normalize_dob(date_part)
            if not dob_norm:
                return False, None, "DOB unparseable or in the future. Expected MM-DD-YYYY (or MM/DD/YYYY or YYYY-MM-DD)."
            first, last = nm
            display = f"{first.title()} {last.title()}"
            return True, {
                "method": "name_dob",
                "first_name": first,
                "last_name": last,
                "display_name": display,
                "dob": dob_norm
            }, None

        return False, None, "Input not recognized. Allowed formats: '#########/##' or 'First Last, MM-DD-YYYY' (comma required)."

    return False, None, "Unsupported input type. Provide either a string or a dict-like object."
