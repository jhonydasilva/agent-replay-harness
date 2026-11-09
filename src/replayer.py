"""Replay recorded LLM/tool responses; reject unexpected external interactions."""

from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from examples.fake_tools import FakeTools
from src.agent import DemoAgent
from src.comparator import compare_decisions
from src.recorder import _utc_now
from src.trace_schema import validate_trace


class ReplayMismatchError(RuntimeError):
    """Raised when strict replay cannot follow the recorded interaction sequence."""


@dataclass
class ReplayResult:
    trace: dict[str, Any]
    comparison: dict[str, Any]
    outcome: str


class _ReplayGateway:
    def __init__(self, baseline: dict[str, Any], injector: Any = None):
        self.baseline = baseline
        self.injector = injector
        self.injected = False
        self.fixtures = FakeTools()
        self.interactions = [
            event
            for event in baseline["events"]
            if event["type"] in {"llm.call", "tool.call"}
        ]
        self.cursor = 0
        self.trace: dict[str, Any] = {
            "schema_version": baseline["schema_version"],
            "run_id": uuid4().hex,
            "agent_version": baseline["agent_version"],
            "started_at": _utc_now(),
            "input": baseline["input"],
            "mode": "inject" if injector else "replay",
            "source_run_id": baseline["run_id"],
            "events": [],
        }
        if injector:
            self.trace["fault"] = deepcopy(injector.specification)

    def _append(self, kind: str, **fields: Any) -> None:
        self.trace["events"].append(
            {
                "seq": len(self.trace["events"]) + 1,
                "type": kind,
                "timestamp": _utc_now(),
                **deepcopy(fields),
            }
        )

    def _call(self, kind: str, request: dict[str, Any]) -> dict[str, Any]:
        if self.injected:
            # The new branch cannot be read from the old tape. Only fixed tool fixtures are allowed.
            if kind == "llm.call":
                # TODO: support explicitly recorded alternate LLM branches.
                raise ReplayMismatchError("unsupported counterfactual llm.call after injected fault")
            response = self.fixtures.invoke(request["name"], request["arguments"])
            self._append(kind, request=request, response=response)
            return deepcopy(response)

        if self.cursor >= len(self.interactions):
            raise ReplayMismatchError(f"unexpected {kind}: recorded interaction tape exhausted")
        event = self.interactions[self.cursor]
        if event["type"] != kind:
            raise ReplayMismatchError(
                f"unexpected {kind}: expected {event['type']} at seq={event['seq']}"
            )
        if event["request"] != request:
            raise ReplayMismatchError(f"{kind} request mismatch at recorded seq={event['seq']}")
        self.cursor += 1
        response = deepcopy(event["response"])
        if self.injector and self.injector.matches(event):
            response = deepcopy(self.injector.specification["replacement_response"])
            self.injected = True
        self._append(kind, request=request, response=response)
        return deepcopy(response)

    def llm_call(self, request: dict[str, Any]) -> dict[str, Any]:
        return self._call("llm.call", request)

    def tool_call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._call("tool.call", {"name": name, "arguments": arguments})

    def decision(self, name: str, *, outcome: str | None = None, tool: str | None = None) -> None:
        fields = {"decision": name}
        if outcome is not None:
            fields["outcome"] = outcome
        if tool is not None:
            fields["tool"] = tool
        self._append("agent.decision", **fields)


class Replayer:
    def __init__(self, trace: dict[str, Any], fault: dict[str, Any] | None = None):
        self.baseline = deepcopy(validate_trace(trace))
        self.fault = fault

    def execute(self) -> ReplayResult:
        injector = None
        if self.fault is not None:
            from src.fault_injector import FaultInjector

            injector = FaultInjector(self.baseline, self.fault)
        gateway = _ReplayGateway(self.baseline, injector)
        outcome = DemoAgent().run(self.baseline["input"], gateway)
        if injector and not gateway.injected:
            raise ReplayMismatchError("fault target was validated but not reached during replay")
        if injector is None and gateway.cursor != len(gateway.interactions):
            raise ReplayMismatchError("recorded interaction tape contains unconsumed calls")
        comparison = compare_decisions(self.baseline, gateway.trace)
        if injector is None and not comparison["identical"]:
            raise ReplayMismatchError(
                f"strict replay decision mismatch: {comparison['first_divergence']}"
            )
        gateway.trace["comparison"] = deepcopy(comparison)
        validate_trace(gateway.trace)
        return ReplayResult(trace=gateway.trace, comparison=comparison, outcome=outcome)
