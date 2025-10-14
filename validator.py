# tools/validator.py
"""
Strict validator for HMM call-prep with MM/DD/YYYY acceptance.

FORMAT 1 (IDs):
 - "050028449/00"  -> subscriber_id="050028449", member_id="00"
 - "05002844900"   -> interpreted as 11-digit -> split into 9/2

FORMAT 2 (conversational, comma-delimited):
 - "Raja Panda, 04-22-1980"  OR "Raja Panda, 04/22/1980" OR "Raja Panda, 1980-04-22"
   -> date parsed permissively and normalized to MM-DD-YYYY (hyphen)

Returns (bool valid, payload_dict or None, error_str or None)
"""

import re
from typing import Any, Dict, Optional, Tuple
from datetime import datetime, date

IdentityResult = Tuple[bool, Optional[Dict[str, Any]], Optional[str]]

# Patterns
RE_ID_SLASH = re.compile(r'^\s*(\d{9})[\/\\](\d{2})\s*$')   # "050028449/00"
RE_ID_11DIGIT = re.compile(r'^\s*(\d{11})\s*$')             # "05002844900"
RE_CONVERSATIONAL = re.compile(r'^\s*(?P<name>.+?)\s*,\s*(?P<date>.+?)\s*$')

# Accept these formats (order matters)
_PERMISSIVE_DATE_FORMATS = ["%m-%d-%Y", "%m/%d/%Y", "%Y-%m-%d"]

def _safe_str(v: Any) -> str:
    try:
        return str(v).strip()
    except Exception:
        return ""

def _parse_and_normalize_dob(dob_raw: str) -> Optional[str]:
    """
    Parse date from permissive formats and return normalized 'MM-DD-YYYY'.
    Returns None if unparseable or date is in the future.
    """
    s = _safe_str(dob_raw)
    if not s:
        return None
    parsed = None
    for fmt in _PERMISSIVE_DATE_FORMATS:
        try:
            parsed = datetime.strptime(s, fmt).date()
            break
        except Exception:
            continue
    if not parsed:
        # If parse failed, try replacing slashes/hyphens and parse again (extra permissive)
        alt = s.replace('/', '-')
        for fmt in _PERMISSIVE_DATE_FORMATS:
            try:
                parsed = datetime.strptime(alt, fmt).date()
                break
            except Exception:
                continue
    if not parsed:
        return None
    if parsed > date.today():
        return None
    return parsed.strftime("%m-%d-%Y")  # normalized with hyphens

def _split_name(fullname: str) -> Optional[Tuple[str,str]]:
    """
    Require at least two name parts. Return (first_name_lower, last_name_lower)
    """
    parts = [p for p in (_safe_str(fullname).split()) if p]
    if len(parts) < 2:
        return None
    first = parts[0].lower()
    last = " ".join(parts[1:]).lower()
    return first, last

def validate_input(inp: Any) -> IdentityResult:
    """
    Validate input (string or dict) and return normalized payload.
    Accepts only:
      - ID format: '#########/##' or 11-digit number
      - Conversational: 'First Last, <date>' where date may be MM-DD-YYYY or MM/DD/YYYY or YYYY-MM-DD
    """
    # Dict-like input: support structured fields first
    if isinstance(inp, dict):
        member = inp.get("member_id") or inp.get("memberId") or inp.get("member")
        subscriber = inp.get("subscriber_id") or inp.get("subscriberId") or inp.get("subscriber")
        suffix = inp.get("suffix") or inp.get("member_suffix") or inp.get("suffix_id")

        if member and subscriber:
            s_sub = _safe_str(subscriber)
            s_suf = _safe_str(suffix or "")
            if not re.fullmatch(r'\d{9}', s_sub):
                return False, None, "subscriber_id must be exactly 9 digits."
            if not re.fullmatch(r'\d{2}', s_suf):
                return False, None, "suffix/member_id must be exactly 2 digits."
            full = f"{s_sub}/{s_suf}"
            return True, {"method":"id","subscriber_id":s_sub,"member_id":s_suf,"full_id":full}, None

        if member:
            m = _safe_str(member)
            mslash = RE_ID_SLASH.fullmatch(m)
            if mslash:
                return True, {"method":"id","subscriber_id":mslash.group(1),"member_id":mslash.group(2),"full_id":f"{mslash.group(1)}/{mslash.group(2)}"}, None
            m11 = RE_ID_11DIGIT.fullmatch(m)
            if m11:
                fid = m11.group(1)
                return True, {"method":"id","subscriber_id":fid[:9],"member_id":fid[-2:],"full_id":f"{fid[:9]}/{fid[-2:]}"}, None
            return False, None, "member_id must be either '9digits/2digits' or 11 digits."

        # Name + DOB structured
        fn = inp.get("first_name") or inp.get("firstName") or inp.get("fname")
        ln = inp.get("last_name") or inp.get("lastName") or inp.get("lname")
        dob = inp.get("dob") or inp.get("date_of_birth") or inp.get("birthdate")
        if fn or ln or dob:
            if not (fn and ln and dob):
                return False, None, "Name+DOB requires first_name, last_name, and dob (MM-DD-YYYY or MM/DD/YYYY)."
            normalized = _parse_and_normalize_dob(dob)
            if not normalized:
                return False, None, "DOB unparseable or in the future. Expected MM-DD-YYYY (or MM/DD/YYYY / YYYY-MM-DD)."
            first, last = _split_name(f"{fn} {ln}")
            if not first:
                return False, None, "Name must include at least first and last name."
            display_name = f"{first.title()} {last.title()}"
            return True, {"method":"name_dob","first_name":first,"last_name":last,"display_name":display_name,"dob":normalized}, None

        raw = inp.get("text") or inp.get("query") or inp.get("message")
        if isinstance(raw, str):
            return validate_input(raw)

        return False, None, "Dict input did not contain acceptable fields. Provide member/subscriber or first_name/last_name/dob or text."

    # String input handling
    if isinstance(inp, str):
        s = inp.strip()

        # ID with slash
        m_id = RE_ID_SLASH.search(s)
        if m_id:
            sub = m_id.group(1)
            mem = m_id.group(2)
            return True, {"method":"id","subscriber_id":sub,"member_id":mem,"full_id":f"{sub}/{mem}"}, None

        # 11-digit
        m_11 = RE_ID_11DIGIT.search(s)
        if m_11:
            fid = m_11.group(1)
            return True, {"method":"id","subscriber_id":fid[:9],"member_id":fid[-2:],"full_id":f"{fid[:9]}/{fid[-2:]}"}, None

        # Conversational "name, date" (comma required)
        conv = RE_CONVERSATIONAL.match(s)
        if conv:
            name_part = conv.group("name")
            date_part = conv.group("date")
            name_split = _split_name(name_part)
            if not name_split:
                return False, None, "Name must include at least first and last name, e.g., 'Raja Panda, 04-22-1980'."
            normalized_dob = _parse_and_normalize_dob(date_part)
            if not normalized_dob:
                return False, None, "DOB unparseable or in the future. Expected MM-DD-YYYY (or MM/DD/YYYY / YYYY-MM-DD)."
            first, last = name_split
            display_name = f"{first.title()} {last.title()}"
            return True, {"method":"name_dob","first_name":first,"last_name":last,"display_name":display_name,"dob":normalized_dob}, None

        return False, None, "Input not recognized. Allowed: '#########/##' or 'First Last, MM-DD-YYYY' (comma required)."

    return False, None, "Unsupported input type. Provide a string or dict."
