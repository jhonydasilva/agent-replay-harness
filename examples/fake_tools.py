"""Deterministic in-memory catalog and cache fixtures."""

from typing import Any


class FakeTools:
    def invoke(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "catalog.lookup":
            return {"status": "ok", "data": {"sku": arguments["sku"], "available": True}}
        if name == "cache.lookup":
            return {
                "status": "ok",
                "data": {"sku": arguments["sku"], "available": True, "source": "cache"},
            }
        raise ValueError(f"unknown fixture tool: {name}")
