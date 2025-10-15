# tools/validator.py
"""
Validator for HMM Call-Prep — conversational-only.

Recognizes two mutually-exclusive paths within free-text:
  1) Subscriber/Member ID (exactly 9 digits + '/' + 2 digits) anywhere in text
     e.g. "050028449/00" or "show subscriber 050028449/00"

  2) Name + DOB (comma required somewhere before date) in conversational or CSV style:
     - "Raja Panda, 04-22-1980"
     - "Raja,Panda,04/22/1980"
     - Messy names with honorifics/suffixes (SR., JR, ESQ) where the date is present:
       e.g. "give me details of SUBSCRIBER SR.SASTIPROPERT, JR IERONIMIDES?ESQ, 1980-08-08"

Returns:
    (valid: bool, payload: Optional[dict], error: Optional[str])

payload:
  - ID path:
      {
        "method": "id",
        "subscriber_id": "050028449",
        "member_id": "00",
        "full_id": "050028449/00"
      }

  - Name+DOB path:
      {
        "method": "name_dob",
        "first_name": "raja",
        "last_name": "panda",
        "display_name": "Raja Panda",
        "dob": "04-22-1980"
      }
"""

import re
from typing import Any, Dict, Optional, Tuple
from datetime import datetime, date

IdentityResult = Tuple[bool, Optional[Dict[str, Any]], Optional[str]]

# Patterns
_RE_ID_SLASH = re.compile(r'(\d{9})[\/\\](\d{2})')  # 9digits / 2digits anywhere
# We'll find a date pattern then extract name chunks before it; also support CSV-form (First,Last,Date)
_DATE_SEARCH = re.compile(r'(\d{4}-\d{2}-\d{2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})')

# For simpler direct Name,Date matches (First Last, DATE) or CSV First,Last,DATE (captures small/normal names)
_RE_NAME_SIMPLE = re.compile(
    r'(?P<first>[A-Za-z][A-Za-z\'\-\.\s]+?)[\s,]+(?P<last>[A-Za-z][A-Za-z\'\-\.\s]+?)[\s,]+(?P<date>[0-9]{1,4}[-/][0-9]{1,2}[-/][0-9]{2,4})'
)

_DATE_FORMATS = ["%m-%d-%Y", "%m/%d/%Y", "%Y-%m-%d"]

# Common honorifics/labels/suffixes to strip when cleaning messy names
_HONORIFICS = {
    "mr", "mrs", "ms", "dr", "sir", "sr", "sr.", "jr", "jr.", "esq", "esq.", "esquire", "subscriber",
    "attn", "attny", "hon", "hon."
}


# ------------------ helpers ------------------
def _safe_str(v: Any) -> str:
    try:
        return str(v).strip()
    except Exception:
        return ""


def _normalize_dob(raw: str) -> Optional[str]:
    """Return DOB as MM-DD-YYYY or None if invalid/future."""
    s = _safe_str(raw)
    if not s:
        return None
    parsed = None
    # Try standard formats
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


def _clean_name_chunk(chunk: str) -> str:
    """
    Clean a messy name chunk:
      - Remove surrounding phrases like 'subscriber', 'give me details of', etc.
      - Strip honorifics and suffix tokens (SR, JR, ESQ).
      - Remove stray punctuation except apostrophes and hyphens.
      - Collapse spaces.
    """
    s = _safe_str(chunk)
    if not s:
        return ""

    # remove common leading phrases conservatively
    s = re.sub(r'^(give me details of|give me details|show me|show|fetch|find|details of)\s+', '', s, flags=re.I)

    # Tokenize by whitespace and commas, filter out honorifics
    tokens = re.split(r'[\s,]+', s)
    kept = []
    for t in tokens:
        if not t:
            continue
        # strip punctuation except ' and -
        core = re.sub(r"[^\w'\-\.]", '', t)
        if not core:
            continue
        low = core.lower().strip('.')
        if low in _HONORIFICS:
            continue
        kept.append(core)
    cleaned = " ".join(kept)
    # strip leftover punctuation except apostrophe and hyphen
    cleaned = re.sub(r"[^\w'\-\s]", '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def _extract_name_before_date(s: str) -> Optional[tuple]:
    """
    Find a date in s, then capture name candidate from the last 1-2 comma-separated chunks before date.
    Returns (first_lower, last_lower) or None.
    """
    m = _DATE_SEARCH.search(s)
    if not m:
        return None
    date_start = m.start()
    before = s[:date_start].strip()
    if not before:
        return None

    # Split by commas and take the last 2 parts (to handle "A, B C" patterns)
    parts = [p.strip() for p in before.split(',') if p.strip()]
    if not parts:
        return None

    if len(parts) >= 2:
        candidate = parts[-2] + " " + parts[-1]
    else:
        candidate = parts[-1]

    cleaned = _clean_name_chunk(candidate)
    if not cleaned:
        return None

    words = [w for w in cleaned.split() if w]
    if len(words) < 2:
        return None
    first = words[0].lower()
    last = " ".join(words[1:]).lower()
    return first, last


# ------------------ main validator ------------------
def validate_input(inp: Any) -> IdentityResult:
    """
    Validate conversational string input and return payload.

    Returns:
        (True, payload_dict, None)  on success
        (False, None, error_str)    on failure
    """
    if not isinstance(inp, str):
        return False, None, "Validator expects a conversational string input."

    s = inp.strip()
    if not s:
        return False, None, "Empty input."

    # 1) ID path (9digits/2digits) — search anywhere
    m_id = _RE_ID_SLASH.search(s)
    if m_id:
        subscriber_id = m_id.group(1)
        member_id = m_id.group(2)
        return True, {
            "method": "id",
            "subscriber_id": subscriber_id,
            "member_id": member_id,
            "full_id": f"{subscriber_id}/{member_id}"
        }, None

    # 2) Try simple Name+DOB pattern (First Last, date) or CSV First,Last,date
    m_simple = _RE_NAME_SIMPLE.search(s)
    if m_simple:
        first_raw = m_simple.group("first")
        last_raw = m_simple.group("last")
        date_raw = m_simple.group("date")
        dob_norm = _normalize_dob(date_raw)
        if not dob_norm:
            return False, None, "DOB unparseable or invalid."
        first = first_raw.strip().lower()
        last = last_raw.strip().lower()
        display = f"{first.title()} {last.title()}"
        return True, {
            "method": "name_dob",
            "first_name": first,
            "last_name": last,
            "display_name": display,
            "dob": dob_norm
        }, None

    # 3) More robust extraction: find date, extract last name chunks before it, clean
    name_pair = _extract_name_before_date(s)
    if name_pair:
        first, last = name_pair
        # find date substring to normalize
        md = _DATE_SEARCH.search(s)
        date_part = md.group(1) if md else ""
        dob_norm = _normalize_dob(date_part)
        if not dob_norm:
            return False, None, "DOB unparseable or invalid."
        display = f"{first.title()} {last.title()}"
        return True, {
            "method": "name_dob",
            "first_name": first,
            "last_name": last,
            "display_name": display,
            "dob": dob_norm
        }, None

    return False, None, (
        "Input not recognized. Provide either:\n"
        "- Subscriber ID: 9 digits + '/' + 2 digits, e.g. 050028449/00\n"
        "- Name + DOB: 'First Last, MM-DD-YYYY' or 'First,Last,MM/DD/YYYY'"
    )
