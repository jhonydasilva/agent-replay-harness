"""Capture local LLM and tool calls as an ordered trace."""

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from src.trace_schema import write_trace

SENSITIVE_FIELDS = {"api_key", "authorization", "password", "secret", "token", "access_token"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_copy(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if key.lower() in SENSITIVE_FIELDS else _safe_copy(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_safe_copy(item) for item in value]
    return json.loads(json.dumps(value, allow_nan=False))


class Recorder:
    def __init__(self, llm: Any, tools: Any, input_text: str, agent_version: str = "0.1.0"):
        self.llm = llm
        self.tools = tools
        self.trace: dict[str, Any] = {
            "schema_version": "1.0",
            "run_id": uuid4().hex,
            "agent_version": agent_version,
            "started_at": _utc_now(),
            "input": input_text,
            "mode": "record",
            "events": [],
        }

    def _append(self, kind: str, **fields: Any) -> None:
        self.trace["events"].append(
            {
                "seq": len(self.trace["events"]) + 1,
                "type": kind,
                "timestamp": _utc_now(),
                **_safe_copy(fields),
            }
        )

    def llm_call(self, request: dict[str, Any]) -> dict[str, Any]:
        response = self.llm.complete(request)
        self._append("llm.call", request=request, response=response)
        return response

    def tool_call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        response = self.tools.invoke(name, arguments)
        self._append("tool.call", request={"name": name, "arguments": arguments}, response=response)
        return response

    def decision(self, name: str, *, outcome: str | None = None, tool: str | None = None) -> None:
        fields: dict[str, str] = {"decision": name}
        if outcome is not None:
            fields["outcome"] = outcome
        if tool is not None:
            fields["tool"] = tool
        self._append("agent.decision", **fields)

    def save(self, path: str) -> None:
        write_trace(path, self.trace)
