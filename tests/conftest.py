import pytest

from examples.fake_llm import FakeLLM
from examples.fake_tools import FakeTools
from src.agent import DemoAgent
from src.recorder import Recorder


@pytest.fixture
def recorded_trace():
    input_text = "Look up product SKU-123"
    recorder = Recorder(FakeLLM(), FakeTools(), input_text)
    assert DemoAgent().run(input_text, recorder) == "success"
    return recorder.trace
