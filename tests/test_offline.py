"""Guard against accidentally introducing outbound calls in the MVP core."""

import json
import socket
from pathlib import Path

from examples.fake_llm import FakeLLM
from examples.fake_tools import FakeTools
from src.agent import DemoAgent
from src.recorder import Recorder
from src.replayer import Replayer


def test_record_replay_and_all_faults_work_with_socket_connections_forbidden(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("the demo must not attempt a network connection")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)

    text = "Look up product SKU-123"
    recorder = Recorder(FakeLLM(), FakeTools(), text)
    assert DemoAgent().run(text, recorder) == "success"
    assert Replayer(recorder.trace).execute().comparison["identical"]

    for name in ("retry", "fallback", "fail_fast"):
        fault_path = Path("examples/faults") / f"{name}.json"
        fault = json.loads(fault_path.read_text(encoding="utf-8"))
        assert not Replayer(recorder.trace, fault=fault).execute().comparison["identical"]
