"""Record a real execution of the local synthetic demo agent."""

import argparse

from examples.fake_llm import FakeLLM
from examples.fake_tools import FakeTools
from src.agent import DemoAgent
from src.recorder import Recorder

INPUT_TEXT = "Look up product SKU-123"


def record_example(output: str) -> dict:
    recorder = Recorder(FakeLLM(), FakeTools(), INPUT_TEXT)
    outcome = DemoAgent().run(INPUT_TEXT, recorder)
    recorder.save(output)
    print(f"Recorded {len(recorder.trace['events'])} events: {output}; outcome={outcome}")
    return recorder.trace


def main() -> None:
    parser = argparse.ArgumentParser(description="Record the offline demo agent")
    parser.add_argument("--output", default="examples/traces/success.json")
    args = parser.parse_args()
    record_example(args.output)


if __name__ == "__main__":
    main()
