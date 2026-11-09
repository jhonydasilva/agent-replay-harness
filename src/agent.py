"""One small agent with explicit deterministic recovery rules."""

from typing import Any


class DemoAgent:
    def run(self, input_text: str, gateway: Any) -> str:
        llm_result = gateway.llm_call({"messages": [{"role": "user", "content": input_text}]})
        calls = llm_result["tool_calls"]
        if len(calls) != 1:
            gateway.decision("fail_fast", outcome="failure")
            return "failure"

        call = calls[0]
        name, arguments = call["name"], call["arguments"]
        gateway.decision("call_tool", tool=name)
        result = gateway.tool_call(name, arguments)
        if result["status"] == "ok":
            gateway.decision("finish", outcome="success")
            return "success"

        error = result["error"]
        if error["code"] == "SERVICE_UNAVAILABLE" and error["retryable"]:
            gateway.decision("retry", tool=name)
            retry_result = gateway.tool_call(name, arguments)
            if retry_result["status"] == "ok":
                gateway.decision("finish", outcome="success")
                return "success"
        elif error["code"] == "TIMEOUT":
            gateway.decision("fallback", tool="cache.lookup")
            fallback_result = gateway.tool_call("cache.lookup", arguments)
            if fallback_result["status"] == "ok":
                gateway.decision("finish", outcome="success")
                return "success"

        gateway.decision("fail_fast", outcome="failure")
        return "failure"
