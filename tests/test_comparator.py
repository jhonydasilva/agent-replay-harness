import copy

from src.comparator import compare_decisions, normalized_decisions


def test_comparison_ignores_timestamps_and_identifiers(recorded_trace):
    changed = copy.deepcopy(recorded_trace)
    changed["run_id"] = "different"
    for event in changed["events"]:
        event["timestamp"] = "2099-01-01T00:00:00Z"
    assert compare_decisions(recorded_trace, changed)["identical"] is True


def test_comparison_reports_first_different_decision(recorded_trace):
    changed = copy.deepcopy(recorded_trace)
    changed["events"][-1]["decision"] = "fail_fast"
    summary = compare_decisions(recorded_trace, changed)
    assert summary["first_divergence"]["decision_index"] == 2
    assert summary["first_divergence"]["original"]["decision"] == "finish"


def test_comparison_detects_missing_decision(recorded_trace):
    changed = copy.deepcopy(recorded_trace)
    changed["events"] = changed["events"][:-1]
    assert compare_decisions(recorded_trace, changed)["identical"] is False
    assert len(normalized_decisions(changed)) == 1
