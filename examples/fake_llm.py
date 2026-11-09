"""A fixed LLM-like decision used only for the offline example."""

from typing import Any


class FakeLLM:
    def complete(self, request: dict[str, Any]) -> dict[str, Any]:
        prompt = request["messages"][-1]["content"]
        if prompt != "Look up product SKU-123":
            raise ValueError("the demo LLM supports only the synthetic SKU-123 request")
        return {
            "tool_calls": [
                {"id": "call-001", "name": "catalog.lookup", "arguments": {"sku": "SKU-123"}}
            ]
        }
