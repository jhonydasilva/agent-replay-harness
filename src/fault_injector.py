"""Validate and target a single deterministic tool-response replacement."""

from typing import Any

from src.trace_schema import TraceValidationError, validate_tool_response


class FaultSpecValidationError(ValueError):
    """Raised when a fault file violates its schema."""


class FaultTargetNotFound(FaultSpecValidationError):
    """Raised when target_seq does not exist in the trace."""


class FaultEventTypeMismatch(FaultSpecValidationError):
    """Raised when event_type does not match the selected trace event."""


class FaultInjector:
    def __init__(self, trace: dict[str, Any], specification: dict[str, Any]):
        if not isinstance(specification, dict):
            raise FaultSpecValidationError("fault specification must be a JSON object")
        required = {"target_seq", "event_type", "replacement_response"}
        if specification.keys() != required:
            raise FaultSpecValidationError(
                f"fault specification requires exactly: {', '.join(sorted(required))}"
            )
        seq = specification["target_seq"]
        if type(seq) is not int or seq < 1:
            raise FaultSpecValidationError("target_seq must be a positive integer")
        if specification["event_type"] != "tool.call":
            raise FaultSpecValidationError("MVP faults may only target event_type='tool.call'")
        matching = next((event for event in trace["events"] if event["seq"] == seq), None)
        if matching is None:
            raise FaultTargetNotFound(f"FaultTargetNotFound: event seq={seq} does not exist")
        if matching["type"] != specification["event_type"]:
            raise FaultEventTypeMismatch(
                "FaultEventTypeMismatch: "
                f"seq={seq} expected {specification['event_type']}, "
                f"found {matching['type']}"
            )
        try:
            validate_tool_response(specification["replacement_response"])
        except TraceValidationError as exc:
            raise FaultSpecValidationError(f"invalid replacement_response: {exc}") from exc
        self.specification = specification

    def matches(self, event: dict[str, Any]) -> bool:
        return (
            event["seq"] == self.specification["target_seq"]
            and event["type"] == self.specification["event_type"]
        )
