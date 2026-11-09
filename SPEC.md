# Technical specification v0.3

**Objective:** Capture a single LLM-style agent execution, reproduce the recorded decision sequence without live calls, and introduce controlled tool failures to inspect deterministic recovery. This is not a production integration or an evaluation of model quality.

## Trace contract

One UTF-8 JSON document per run. Required top-level keys: `schema_version` (`"1.0"`), `run_id`, `agent_version`, `started_at`, `input`, `mode` (`record`, `replay`, `inject`), and `events`. Every event has a consecutive integer `seq`, `timestamp`, and a `type` from `llm.call`, `tool.call`, `agent.decision`. LLM/tool events have `request` and `response`; decision events have `decision` and optional `tool`/`outcome`. Timestamps and generated run IDs are excluded from semantic comparisons. A trace with malformed order or response is rejected.

## Processing and fault contract

```text
fake LLM + local tools -> Recorder -> JSON trace
                                      |
                                strict Replayer
                              /                \
                       recorded outputs      FaultInjector
                              \                /
                               agent decisions
                                      |
                                  Comparator
                                      |
                             CLI report / benchmark
```

Recording captures requests/responses and decisions as they happen. Strict replay checks call order and arguments, then substitutes recorded LLM/tool responses. It fails if new calls appear or decisions differ. Injected replay replaces one tool response and uses explicit deterministic local fixtures for subsequent tool calls. It does not fabricate a new LLM decision.

Fault input contains **exactly** `target_seq` (positive integer), `event_type` (`"tool.call"`), and `replacement_response` (complete tool response with `status: "ok"` and object `data`, or `status: "error"` with `error.code`, `error.message`, and `error.retryable`). An absent sequence, different event type, or invalid replacement causes a named error and nonzero CLI exit. See [retry.json](examples/faults/retry.json) for a concrete fixture targeting sequence 3.

Recovery scenarios: **retry** (simulated 503, then catalog fixture success), **fallback** (timeout, then cache fixture success), and **fail-fast** (invalid response, deterministic failure).

## Definition of done

| # | Pass condition | Measured by |
|---|---|---|
| 1 | In a clean Git clone, `python -m venv .venv` then `make setup && make demo` run without preconfigured application environment variables, with no network except dependency installation, and demo exits 0. | Clean-clone setup/demo log |
| 2 | At least 12 pytest tests pass, covering all three fault scenarios. | `make test` output |
| 3 | 100% identical normalized decisions when replaying `success.json` across measured runs. | **#5** benchmark |
| 4 | Retry injection causes an intentional decision difference reported by the comparator. | **#5** benchmark and CLI |
| 5 | `benchmarks/run_benchmarks.py` executes N strict and N injected replays, measures latency/determinism, and writes `RESULTS.md` itself. | Generated `RESULTS.md` and benchmark log |

## Risks and boundaries

Timestamps/IDs may vary, so compare semantic decisions. External tools can drift, so replay substitutes recorded outputs or explicit local fixtures. A new post-fault LLM call is an unsupported counterfactual and must error, not invoke a model. **This harness does not prove production reliability:** it proves reproducibility for a specific recorded execution and determinism for this defined recovery policy. Residual nondeterminism and failed acceptance criteria are disclosed in [README.md](README.md).

Out of scope: multiple agent frameworks, async/distributed agents, production services, authentication, a web UI, and genuine live-model responses after faults.
