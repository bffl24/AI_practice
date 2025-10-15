# test_validator.py
"""
Standalone test script for tools.validator
Run directly:  python test_validator.py

Covers:
 - Plain ID
 - Conversational ID
 - Name + DOB (conversational)
 - Name + DOB (CSV-style)
 - Complex messy name with honorifics/suffixes
 - Invalid input
"""

from tools.validator import validate_input


def run_test_case(name, input_str):
    """Run a single test and print result clearly."""
    print("\n" + "=" * 80)
    print(f"TEST CASE: {name}")
    print(f"Input: {input_str!r}")

    ok, payload, err = validate_input(input_str)
    print("Valid:", ok)
    print("Payload:", payload)
    print("Error:", err)

    if ok:
        print(f"✅ PASS — recognized as {payload.get('method')}")
    else:
        print("❌ FAIL —", err)
    return ok


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("🔍 Starting manual validator tests (no pytest required)...")

    tests = [
        ("Plain ID", "050028449/00"),
        ("Conversational ID", "give me details for subscriber 050028449/00 please"),
        ("Name+DOB (Conversational)", "Raja Panda, 04/22/1980"),
        ("Name+DOB (CSV style)", "Raja,Panda,04/22/1980"),
        ("Complex Messy Name", " give me details of SUBSCRIBER SR.SASTIPROPERT, JR IERONIMIDES?ESQ, 1980-08-08"),
        ("Invalid Input", "Raja"),
    ]

    passed = 0
    for name, case in tests:
        if run_test_case(name, case):
            passed += 1

    print("\n" + "=" * 80)
    print(f"✅ Completed. Passed {passed}/{len(tests)} tests.")
    print("=" * 80)
