# tests/test_validator.py
import pytest
from tools.validator import validate_input

def test_plain_id():
    ok, payload, err = validate_input("050028449/00")
    assert ok is True
    assert payload["method"] == "id"
    assert payload["subscriber_id"] == "050028449"
    assert payload["member_id"] == "00"

def test_conversational_id():
    ok, payload, err = validate_input("give me details for subscriber 050028449/00 please")
    assert ok is True
    assert payload["method"] == "id"
    assert payload["subscriber_id"] == "050028449"

def test_name_dob_conversational():
    ok, payload, err = validate_input("Raja Panda, 04/22/1980")
    assert ok is True
    assert payload["method"] == "name_dob"
    assert payload["first_name"] == "raja"
    assert payload["last_name"] == "panda"
    assert payload["dob"] == "04-22-1980"

def test_name_dob_csv():
    ok, payload, err = validate_input("Raja,Panda,04/22/1980")
    assert ok is True
    assert payload["method"] == "name_dob"
    assert payload["first_name"] == "raja"
    assert payload["last_name"] == "panda"
    assert payload["dob"] == "04-22-1980"

def test_complex_messy_name():
    s = " give me details of SUBSCRIBER SR.SASTIPROPERT, JR IERONIMIDES?ESQ, 1980-08-08"
    ok, payload, err = validate_input(s)
    assert ok is True, f"Failed to parse complex input: {err}"
    assert payload["method"] == "name_dob"
    # payload should extract something like 'sastipropert' and 'ieronimides'
    assert "first_name" in payload and "last_name" in payload
    assert payload["dob"] == "08-08-1980"

def test_invalid_input():
    ok, payload, err = validate_input("Raja")
    assert ok is False
    assert payload is None
    assert isinstance(err, str)
