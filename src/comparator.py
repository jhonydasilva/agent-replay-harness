"""Compare semantic agent decisions without timestamps or execution identifiers."""

from typing import Any


def normalized_decisions(trace: dict[str, Any]) -> list[dict[str, str]]:
    decisions = []
    for event in trace["events"]:
        if event["type"] != "agent.decision":
            continue
        entry = {"decision": event["decision"]}
        for key in ("tool", "outcome"):
            if key in event:
                entry[key] = event[key]
        decisions.append(entry)
    return decisions


def compare_decisions(baseline: dict[str, Any], replay: dict[str, Any]) -> dict[str, Any]:
    original = normalized_decisions(baseline)
    observed = normalized_decisions(replay)
    divergence = None
    for index in range(max(len(original), len(observed))):
        before = original[index] if index < len(original) else None
        after = observed[index] if index < len(observed) else None
        if before != after:
            divergence = {"decision_index": index + 1, "original": before, "replay": after}
            break
    return {
        "identical": divergence is None,
        "baseline_count": len(original),
        "replay_count": len(observed),
        "first_divergence": divergence,
    }
