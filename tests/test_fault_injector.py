import copy
import json
from pathlib import Path

import pytest

from src.fault_injector import (
    FaultEventTypeMismatch,
    FaultInjector,
    FaultSpecValidationError,
    FaultTargetNotFound,
)
from src.replayer import Replayer

FAULTS = Path("examples/faults")


def _fault(name):
    return json.loads((FAULTS / f"{name}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("scenario", "expected_decision", "expected_outcome"),
    [
        ("retry", "retry", "success"),
        ("fallback", "fallback", "success"),
        ("fail_fast", "fail_fast", "failure"),
    ],
)
def test_injected_fault_changes_agent_decision_as_expected(
    recorded_trace, scenario, expected_decision, expected_outcome
):
    result = Replayer(recorded_trace, fault=_fault(scenario)).execute()
    assert result.outcome == expected_outcome
    assert result.comparison["identical"] is False
    assert result.comparison["first_divergence"]["decision_index"] == 2
    decisions = [e["decision"] for e in result.trace["events"] if e["type"] == "agent.decision"]
    assert expected_decision in decisions


def test_retry_uses_recorded_target_and_then_local_fixture(recorded_trace):
    result = Replayer(recorded_trace, fault=_fault("retry")).execute()
    tools = [e for e in result.trace["events"] if e["type"] == "tool.call"]
    assert len(tools) == 2
    assert tools[0]["response"]["error"]["code"] == "SERVICE_UNAVAILABLE"
    assert tools[1]["response"]["status"] == "ok"


def test_fallback_uses_local_cache_fixture(recorded_trace):
    result = Replayer(recorded_trace, fault=_fault("fallback")).execute()
    tools = [e for e in result.trace["events"] if e["type"] == "tool.call"]
    assert tools[-1]["request"]["name"] == "cache.lookup"
    assert tools[-1]["response"]["data"]["source"] == "cache"


def test_fault_for_nonexistent_seq_fails_loudly(recorded_trace):
    fault = _fault("retry")
    fault["target_seq"] = 99
    with pytest.raises(FaultTargetNotFound, match="seq=99"):
        Replayer(recorded_trace, fault=fault).execute()


def test_fault_on_llm_event_reports_type_mismatch(recorded_trace):
    fault = _fault("retry")
    fault["target_seq"] = 1
    with pytest.raises(FaultEventTypeMismatch, match="found llm.call"):
        Replayer(recorded_trace, fault=fault).execute()


def test_fault_rejects_invalid_response_contract(recorded_trace):
    fault = _fault("retry")
    fault["replacement_response"] = {"status": "error"}
    with pytest.raises(FaultSpecValidationError, match="invalid replacement_response"):
        FaultInjector(recorded_trace, fault)


def test_fault_rejects_boolean_seq_even_though_bool_is_int(recorded_trace):
    fault = _fault("retry")
    fault["target_seq"] = True
    with pytest.raises(FaultSpecValidationError, match="positive integer"):
        FaultInjector(recorded_trace, fault)


def test_original_trace_is_not_mutated_by_injection(recorded_trace):
    original = copy.deepcopy(recorded_trace)
    Replayer(recorded_trace, fault=_fault("fail_fast")).execute()
    assert recorded_trace == original
