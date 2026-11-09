import copy

import pytest

from examples.fake_llm import FakeLLM
from src.agent import DemoAgent
from src.recorder import Recorder
from src.trace_schema import TraceValidationError, read_trace, validate_trace


class FailingTools:
    def invoke(self, name, arguments):
        return {
            "status": "error",
            "error": {
                "code": "INVALID_RESPONSE",
                "message": "Malformed fixture",
                "retryable": False,
            },
        }


def test_recording_has_ordered_llm_tool_and_decision_events(recorded_trace):
    assert [event["seq"] for event in recorded_trace["events"]] == [1, 2, 3, 4]
    assert [event["type"] for event in recorded_trace["events"]] == [
        "llm.call",
        "agent.decision",
        "tool.call",
        "agent.decision",
    ]
    assert recorded_trace["events"][2]["request"]["name"] == "catalog.lookup"


def test_recording_roundtrip_json(tmp_path, recorded_trace):
    from src.trace_schema import write_trace

    path = tmp_path / "trace.json"
    write_trace(path, recorded_trace)
    assert read_trace(path) == recorded_trace


def test_recorder_captures_fail_fast_path():
    input_text = "Look up product SKU-123"
    recorder = Recorder(FakeLLM(), FailingTools(), input_text)
    assert DemoAgent().run(input_text, recorder) == "failure"
    assert recorder.trace["events"][-1]["decision"] == "fail_fast"
    assert recorder.trace["events"][-1]["outcome"] == "failure"


def test_schema_rejects_missing_event_number(recorded_trace):
    broken = copy.deepcopy(recorded_trace)
    broken["events"][1]["seq"] = 6
    with pytest.raises(TraceValidationError, match="consecutive"):
        validate_trace(broken)


def test_schema_rejects_invalid_tool_response(recorded_trace):
    broken = copy.deepcopy(recorded_trace)
    broken["events"][2]["response"] = {"status": "maybe"}
    with pytest.raises(TraceValidationError, match="status"):
        validate_trace(broken)


def test_recorder_redacts_nested_secret_fields():
    input_text = "Look up product SKU-123"
    recorder = Recorder(FakeLLM(), FailingTools(), input_text)
    recorder.decision("check", tool="catalog.lookup")
    recorder._append("agent.decision", decision="secret_test", extra={"authorization": "Bearer X"})
    assert recorder.trace["events"][-1]["extra"]["authorization"] == "[REDACTED]"
