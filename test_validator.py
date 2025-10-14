from .tools.helper.validator import validate_input

def test_id_with_slash():
    ok, p, e = validate_input("Please pull 050028449/00 for me")
    assert ok and p["method"]=="id" and p["subscriber_id"]=="050028449" and p["member_id"]=="00"

def test_11_digits():
    ok, p, e = validate_input("05002844900")
    assert ok and p["full_id"]=="050028449/00"

def test_conversational_mm_slash():
    ok, p, e = validate_input("raja panda, 04/22/1980")
    assert ok and p["method"]=="name_dob" and p["dob"]=="04-22-1980" and p["first_name"]=="raja"

def test_conversational_mm_hyphen():
    ok, p, e = validate_input("Raja Panda, 04-22-1980")
    assert ok and p["display_name"]=="Raja Panda" and p["dob"]=="04-22-1980"

def test_conversational_iso_input():
    ok, p, e = validate_input("Raja Panda, 1980-04-22")
    assert ok and p["dob"]=="04-22-1980"

def test_invalid_date_future():
    future = "John Doe, 12-31-2999"
    ok, p, e = validate_input(future)
    assert not ok

def test_invalid_conversational_no_comma():
    ok, p, e = validate_input("Raja Panda 04-22-1980")
    assert not ok
