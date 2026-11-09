"""Validation and I/O for versioned trace documents."""

import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
EVENT_TYPES = {"llm.call", "tool.call", "agent.decision"}


class TraceValidationError(ValueError):
    """Raised when a trace violates the v1 contract."""


def validate_tool_response(response: Any) -> None:
    if not isinstance(response, dict) or response.get("status") not in ("ok", "error"):
        raise TraceValidationError("tool response must have status 'ok' or 'error'")
    if response["status"] == "ok" and not isinstance(response.get("data"), dict):
        raise TraceValidationError("successful tool response must include object 'data'")
    if response["status"] == "error":
        error = response.get("error")
        if not isinstance(error, dict):
            raise TraceValidationError("failed tool response must include object 'error'")
        if not isinstance(error.get("code"), str) or not error["code"]:
            raise TraceValidationError("tool error requires nonempty string 'code'")
        if not isinstance(error.get("message"), str):
            raise TraceValidationError("tool error requires string 'message'")
        if not isinstance(error.get("retryable"), bool):
            raise TraceValidationError("tool error requires boolean 'retryable'")


def validate_trace(trace: Any) -> dict[str, Any]:
    if not isinstance(trace, dict):
        raise TraceValidationError("trace must be a JSON object")
    if trace.get("schema_version") != SCHEMA_VERSION:
        raise TraceValidationError(f"unsupported schema_version: {trace.get('schema_version')!r}")
    for key in ("run_id", "agent_version", "started_at", "input"):
        if not isinstance(trace.get(key), str) or not trace[key]:
            raise TraceValidationError(f"trace requires nonempty string {key!r}")
    if trace.get("mode") not in ("record", "replay", "inject"):
        raise TraceValidationError("trace mode must be record, replay, or inject")
    events = trace.get("events")
    if not isinstance(events, list) or not events:
        raise TraceValidationError("trace events must be a nonempty list")
    for expected, event in enumerate(events, start=1):
        if not isinstance(event, dict):
            raise TraceValidationError(f"event {expected} must be an object")
        if type(event.get("seq")) is not int or event["seq"] != expected:
            raise TraceValidationError(f"event sequence must be consecutive: expected {expected}")
        kind = event.get("type")
        if not isinstance(kind, str) or kind not in EVENT_TYPES:
            raise TraceValidationError(f"event {expected} has invalid type: {kind!r}")
        if not isinstance(event.get("timestamp"), str):
            raise TraceValidationError(f"event {expected} requires a timestamp")
        if kind in {"llm.call", "tool.call"}:
            if not isinstance(event.get("request"), dict):
                raise TraceValidationError(f"event {expected} requires object 'request'")
            if not isinstance(event.get("response"), dict):
                raise TraceValidationError(f"event {expected} requires object 'response'")
        if kind == "tool.call":
            if not isinstance(event["request"].get("name"), str):
                raise TraceValidationError(f"tool event {expected} requires tool name")
            if not isinstance(event["request"].get("arguments"), dict):
                raise TraceValidationError(f"tool event {expected} requires arguments object")
            validate_tool_response(event["response"])
        if kind == "llm.call" and not isinstance(event["response"].get("tool_calls"), list):
            raise TraceValidationError(f"llm event {expected} requires tool_calls list")
        if kind == "agent.decision":
            if not isinstance(event.get("decision"), str) or not event["decision"]:
                raise TraceValidationError(f"decision event {expected} requires a decision")
            if "outcome" in event and event["outcome"] not in {"success", "failure"}:
                raise TraceValidationError(f"decision event {expected} has invalid outcome")
    return trace


def read_trace(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TraceValidationError(f"cannot read trace {path}: {exc}") from exc
    return validate_trace(content)


def write_trace(path: str | Path, trace: dict[str, Any]) -> None:
    validate_trace(trace)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    temporary.write_text(json.dumps(trace, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(target)
