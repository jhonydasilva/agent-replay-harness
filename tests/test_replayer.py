import copy

import pytest

from examples.fake_llm import FakeLLM
from src.agent import DemoAgent
from src.recorder import Recorder
from src.replayer import ReplayMismatchError, Replayer


class PermanentFailureTools:
    def invoke(self, name, arguments):
        return {
            "status": "error",
            "error": {"code": "INVALID_RESPONSE", "message": "Bad payload", "retryable": False},
        }


def test_strict_replay_matches_normalized_decisions(recorded_trace):
    result = Replayer(recorded_trace).execute()
    assert result.outcome == "success"
    assert result.comparison["identical"] is True
    assert result.comparison["baseline_count"] == 2


def test_strict_replay_copies_recorded_llm_and_tool_answers(recorded_trace):
    result = Replayer(recorded_trace).execute()
    baseline_calls = [
        e["response"] for e in recorded_trace["events"] if e["type"] != "agent.decision"
    ]
    replay_calls = [e["response"] for e in result.trace["events"] if e["type"] != "agent.decision"]
    assert baseline_calls == replay_calls


def test_replay_of_recorded_failure_reproduces_fail_fast():
    text = "Look up product SKU-123"
    recorder = Recorder(FakeLLM(), PermanentFailureTools(), text)
    assert DemoAgent().run(text, recorder) == "failure"
    result = Replayer(recorder.trace).execute()
    assert result.outcome == "failure"
    assert result.comparison["identical"] is True
    assert result.trace["events"][-1]["decision"] == "fail_fast"


def test_strict_replay_rejects_mismatched_llm_request(recorded_trace):
    tampered = copy.deepcopy(recorded_trace)
    tampered["events"][0]["request"]["messages"][0]["content"] = "unexpected"
    with pytest.raises(ReplayMismatchError, match="request mismatch"):
        Replayer(tampered).execute()


def test_strict_replay_detects_extra_tool_call_if_trace_lacks_it(recorded_trace):
    tampered = copy.deepcopy(recorded_trace)
    tampered["events"][2]["response"] = {
        "status": "error",
        "error": {"code": "SERVICE_UNAVAILABLE", "message": "temporary", "retryable": True},
    }
    with pytest.raises(ReplayMismatchError, match="unexpected tool.call"):
        Replayer(tampered).execute()
