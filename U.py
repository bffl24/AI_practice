"""
Unit tests for the HMM Call Prep ADK agent (google ADK).

Covers:
- Tool function behavior (hmm_get_data) using realistic aggregator JSON
- Agent registration/config checks
- Prompt invariants (must include the failure message text)

If your agent module isn't at repo-root/agent.py, adjust CANDIDATE_MODULES below.
"""

import inspect
import importlib
import json
from types import SimpleNamespace
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, patch

import pytest


# -------------------------------------------------------------------
# Import the agent module (adjust if path differs)
# -------------------------------------------------------------------
CANDIDATE_MODULES = (
    "agent",                # repo root/agent.py
    "app.agent",            # app/agent.py
    "app.agents.agent",     # app/agents/agent.py
    "src.agent",            # src/agent.py
)


def _import_agent_module():
    """Try to import the agent module from common locations."""
    last_err = None
    for name in CANDIDATE_MODULES:
        try:
            return importlib.import_module(name)
        except Exception as e:
            last_err = e
    raise ImportError(f"Could not import agent module. Tried {CANDIDATE_MODULES}") from last_err


AGENT_MOD = _import_agent_module()


# -------------------------------------------------------------------
# Patch helpers
# -------------------------------------------------------------------
PATCH_TARGETS_AGGREGATOR = [
    "PatientDataAggregator",
    "app.api_client.aggregator.PatientDataAggregator",
    "app.tools.aggregator.PatientDataAggregator",
]

PATCH_TARGETS_CLIENT = [
    "HealthcareAPIClient",
    "app.api_client.client.HealthcareAPIClient",
    "app.tools.client.HealthcareAPIClient",
]


def _resolve_attr(mod, names):
    for n in names:
        if hasattr(mod, n):
            return n
    raise AttributeError(f"None of {names} found in module {mod.__name__}")


def _patch_first_existing(mod, names, replacement):
    target_attr = _resolve_attr(mod, names)
    full = f"{mod.__name__}.{target_attr}"
    p = patch(full, replacement)
    p.start()
    return p, target_attr


# -------------------------------------------------------------------
# Tool context shim
# -------------------------------------------------------------------
def _make_tool_context(state: Optional[Dict[str, Any]] = None):
    ns = SimpleNamespace()
    if state is not None:
        ns.state = state
    return ns


def _call_hmm_get_data(topic: str, tool_context: Optional[Any] = None):
    """Call hmm_get_data with whichever signature it supports."""
    fn = getattr(AGENT_MOD, "hmm_get_data")
    sig = inspect.signature(fn)
    if len(sig.parameters) == 1:
        return fn(topic)
    elif len(sig.parameters) == 2:
        if tool_context is None:
            tool_context = _make_tool_context({})
        return fn(topic, tool_context)
    raise TypeError(
        "hmm_get_data signature unexpected; expected (topic) or (topic, tool_context)."
    )


# -------------------------------------------------------------------
# Pytest fixtures / cleanup
# -------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _stop_patches():
    yield
    patch.stopall()


@pytest.fixture
def aggregator_json_full():
    """Representative aggregator JSON (matches your schema)."""
    return {
        "demographics": {
            "subscriberId": "9675982090000",
            "memberId": "00",
            "firstName": "KINGBIRD",
            "lastName": "PITWICZ",
            "birthDate": "1980-04-17",
            "isFep": False,
            "phoneNumbers": [
                {"phone_type": "Primary", "phone_number": "714313-4556"},
                {"phone_type": "Alternate", "phone_number": "714313-4556"},
            ],
            "doNotCall": True,
        },
        "medical_visits": {
            "pharmacy": [
                {"claimSource": "cvs", "display": "Metformin 100mg"}
            ],
            "emergency": [
                {
                    "claimSource": "er",
                    "claimReceiptDate": "2024-09-17",
                    "claimLastProcessedDate": "2026-04-21",
                    "headerServicedStartDate": "2024-09-11",
                    "headerServicedEndDate": "2024-09-11",
                }
            ],
            "hospitalization": [
                {
                    "claimSource": "Hospital",
                    "claimReceiptDate": "2024-09-17",
                    "claimLastProcessedDate": "2026-04-21",
                    "headerServicedStartDate": "2024-09-11",
                    "headerServicedEndDate": "2024-09-11",
                }
            ],
        },
        "status": {
            "current_status": "Post-Discharge",
            "primary_diagnosis": "Hypertension",
            "next_review_date": "2025-11-20",
            "estimated_discharge_date": None,
        },
    }


# -------------------------------------------------------------------
# Agent object & prompt invariants
# -------------------------------------------------------------------
def test_agent_is_registered_and_has_tool_and_instruction():
    agent_obj = getattr(AGENT_MOD, "hmm_call_prep", None) or getattr(AGENT_MOD, "agent", None)
    assert agent_obj is not None, "Agent object not found (expected `hmm_call_prep` or `agent`)."

    tool_names = [t.__name__ for t in agent_obj.tools]
    assert "hmm_get_data" in tool_names
    assert isinstance(agent_obj.instruction, str) and len(agent_obj.instruction) > 0
    assert isinstance(agent_obj.model, str) and len(agent_obj.model) > 0


def test_instruction_contains_failure_message_and_core_headers():
    agent_obj = getattr(AGENT_MOD, "hmm_call_prep", None) or getattr(AGENT_MOD, "agent", None)
    instr = agent_obj.instruction

    must_have = [
        "Data reception failed, please attempt again.",
        "Patient Identification",
        "Contact Information",
        "Recent Medications",
        "Recent Encounters",
        "Clinical Assessment",
    ]
    for frag in must_have:
        assert frag in instr, f"Prompt missing required fragment: {frag!r}"

    banned = ["{{", "}}", "\t"]
    assert not any(b in instr for b in banned), "Prompt contains placeholders or tabs."


# -------------------------------------------------------------------
# Tool behavior tests (mocking aggregator & client)
# -------------------------------------------------------------------
@pytest.mark.asyncio
async def test_invalid_topic_returns_error_message():
    tool_context = _make_tool_context({"patient_id": "SUB123", "patient_name": "John Smith"})
    _patch_first_existing(AGENT_MOD, PATCH_TARGETS_CLIENT, object())
    agg_mock = SimpleNamespace(get_all_patient_data=AsyncMock(return_value={}))
    _patch_first_existing(AGENT_MOD, PATCH_TARGETS_AGGREGATOR, lambda *a, **k: agg_mock)

    out = await _call_hmm_get_data("unknown_topic", tool_context)
    assert out["status"] == "error"
    assert "not found" in out["data"].lower()
    json.dumps(out)


@pytest.mark.asyncio
async def test_upstream_exception_is_caught_and_masked():
    tool_context = _make_tool_context({"patient_id": "SUB123", "patient_name": "John Smith"})
    _patch_first_existing(AGENT_MOD, PATCH_TARGETS_CLIENT, object())
    agg_mock = SimpleNamespace(get_all_patient_data=AsyncMock(side_effect=RuntimeError("boom")))
    _patch_first_existing(AGENT_MOD, PATCH_TARGETS_AGGREGATOR, lambda *a, **k: agg_mock)

    out = await _call_hmm_get_data("patient_info", tool_context)
    assert out["status"] == "error"
    assert "failed to retrieve data" in out["data"].lower()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "topic, expected_key",
    [
        ("patient_info", "demographics"),
        ("medical_visits", "medical_visits"),
        ("status", "status"),
    ],
)
async def test_happy_path_per_topic_returns_success_and_expected_slice(
    topic, expected_key, aggregator_json_full
):
    tool_context = _make_tool_context({"patient_id": "SUB123", "patient_name": "John Smith"})
    _patch_first_existing(AGENT_MOD, PATCH_TARGETS_CLIENT, object())
    agg_mock = SimpleNamespace(get_all_patient_data=AsyncMock(return_value=aggregator_json_full))
    _patch_first_existing(AGENT_MOD, PATCH_TARGETS_AGGREGATOR, lambda *a, **k: agg_mock)

    out = await _call_hmm_get_data(topic, tool_context)
    assert out["status"] == "success"
    assert out["data"] == aggregator_json_full[expected_key]
    assert out["topic"] == topic
    json.dumps(out)


@pytest.mark.asyncio
async def test_valid_topic_but_no_data_returns_specific_error(aggregator_json_full):
    tool_context = _make_tool_context({"patient_id": "SUB123", "patient_name": "John Smith"})
    broken = dict(aggregator_json_full)
    broken["demographics"] = None

    _patch_first_existing(AGENT_MOD, PATCH_TARGETS_CLIENT, object())
    agg_mock = SimpleNamespace(get_all_patient_data=AsyncMock(return_value=broken))
    _patch_first_existing(AGENT_MOD, PATCH_TARGETS_AGGREGATOR, lambda *a, **k: agg_mock)

    out = await _call_hmm_get_data("patient_info", tool_context)
    assert out["status"] == "error"
    assert "no data available" in out["data"].lower()


@pytest.mark.asyncio
async def test_missing_tool_context_defaults_are_used_and_aggregator_still_called(
    aggregator_json_full,
):
    tool_context = _make_tool_context(None)
    _patch_first_existing(AGENT_MOD, PATCH_TARGETS_CLIENT, object())
    seen_kwargs = {}

    async def _fake_get_all_patient_data(**kwargs):
        seen_kwargs.update(kwargs)
        return aggregator_json_full

    agg_mock = SimpleNamespace(get_all_patient_data=AsyncMock(side_effect=_fake_get_all_patient_data))
    _patch_first_existing(AGENT_MOD, PATCH_TARGETS_AGGREGATOR, lambda *a, **k: agg_mock)

    await _call_hmm_get_data("status", tool_context)
    assert "patient_id" in seen_kwargs and seen_kwargs["patient_id"]
    assert "patient_name" in seen_kwargs and seen_kwargs["patient_name"]
