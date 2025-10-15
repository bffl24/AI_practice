# tests/test_validator.py
"""
Unit tests for tools.validator
Covers:
 - Plain ID
 - Conversational ID
 - Name + DOB (conversational)
 - Name + DOB (CSV-style)
 - Complex messy name with honorifics/suffixes
 - Invalid input
"""

import pytest
from tools.validator import validate_input


def test_plain_id():
    """Simple ID pattern 9 digits/2 digits."""
    ok, payload, err = validate_input("050028449/00")
    print("\nPlain ID =>", ok, payload, err)
    assert ok is True
    assert payload["method"] == "id"
    assert payload["subscriber_id"] == "050028449"
    assert payload["member_id"] == "00"


def test_conversational_id():
    """Conversational phrase containing subscriber ID."""
    ok, payload, err = validate_input("give me details for subscriber 050028449/00 please")
    print("\nConversational ID =>", ok, payload, err)
    assert ok is True
    assert payload["method"] == "id"
    assert payload["subscriber_id"] == "050028449"


def test_name_dob_conversational():
    """Standard name + DOB with space + comma."""
    ok, payload, err = validate_input("Raja Panda, 04/22/1980")
    print("\nName+DOB Conversational =>", ok, payload, err)
    assert ok is True
    assert payload["method"] == "name_dob"
    assert payload["first_name"] == "raja"
    assert payload["last_name"] == "panda"
    assert payload["dob"] == "04-22-1980"


def test_name_dob_csv():
    """CSV-style name + DOB (First,Last,Date)."""
    ok, payload, err = validate_input("Raja,Panda,04/22/1980")
    print("\nName+DOB CSV =>", ok, payload, err)
    assert ok is True
    assert payload["method"] == "name_dob"
    assert payload["first_name"] == "raja"
    assert payload["last_name"] == "panda"
    assert payload["dob"] == "04-22-1980"


def test_complex_messy_name():
    """Messy name with honorifics, suffixes, punctuation, extra words."""
    s = " give me details of SUBSCRIBER SR.SASTIPROPERT, JR IERONIMIDES?ESQ, 1980-08-08"
    ok, payload, err = validate_input(s)
    print("\nComplex Messy Name =>", ok, payload, err)
    assert ok is True, f"Failed to parse complex input: {err}"
    assert payload["method"] == "name_dob"
    # extracted name and date normalized
    assert "first_name" in payload and "last_name" in payload
    assert payload["dob"] == "08-08-1980"


def test_invalid_input():
    """Invalid input should fail gracefully."""
    ok, payload, err = validate_input("Raja")
    print("\nInvalid Input =>", ok, payload, err)
    assert ok is False
    assert payload is None
    assert isinstance(err, str)
