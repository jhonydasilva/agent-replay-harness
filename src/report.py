"""Aggregate local trace outcomes into a small text-based dashboard."""

from pathlib import Path
from typing import Any

from src.trace_schema import read_trace


def trace_outcome(trace: dict[str, Any]) -> str:
    for event in reversed(trace["events"]):
        if event["type"] == "agent.decision" and "outcome" in event:
            return event["outcome"]
    return "unknown"


def summarize_directory(directory: str | Path) -> dict[str, Any]:
    path = Path(directory)
    if not path.is_dir():
        raise ValueError(f"trace directory does not exist: {path}")
    files = sorted(path.glob("*.json"))
    traces = [(file.name, read_trace(file)) for file in files]
    successes = sum(trace_outcome(trace) == "success" for _, trace in traces)
    failures = sum(trace_outcome(trace) == "failure" for _, trace in traces)
    divergences = sum(
        trace.get("comparison", {}).get("identical") is False for _, trace in traces
    )
    return {
        "total": len(traces),
        "recorded": sum(trace["mode"] == "record" for _, trace in traces),
        "replayed": sum(trace["mode"] == "replay" for _, trace in traces),
        "injected": sum(trace["mode"] == "inject" for _, trace in traces),
        "successes": successes,
        "failures": failures,
        "success_rate_percent": round(successes / len(traces) * 100, 2) if traces else 0.0,
        "intentional_divergences": divergences,
        "files": [
            {
                "name": name,
                "mode": trace["mode"],
                "outcome": trace_outcome(trace),
                "first_divergence": trace.get("comparison", {}).get("first_divergence"),
            }
            for name, trace in traces
        ],
    }


def format_report(summary: dict[str, Any]) -> str:
    lines = [
        "Local trace dashboard",
        f"Traces: {summary['total']} (record: {summary['recorded']}, "
        f"replay: {summary['replayed']}, inject: {summary['injected']})",
        f"Success: {summary['successes']}; failure: {summary['failures']}; "
        f"success rate: {summary['success_rate_percent']:.2f}%",
        f"Detected decision divergences: {summary['intentional_divergences']}",
    ]
    for file in summary["files"]:
        diff = file["first_divergence"]
        detail = f" | first diff at decision {diff['decision_index']}" if diff else ""
        lines.append(f"  {file['name']}: {file['mode']} / {file['outcome']}{detail}")
    return "\n".join(lines)
