# Engineering decisions

These decisions define the MVP's reproducibility boundary. They are not claims about the reliability of an arbitrary agent in production.

## 1. Versioned JSON traces instead of SQLite

**Decision:** Keep one trace per file, schema version `1.0`, ordered by consecutive `seq` values.

**Why:** A failure report can attach a readable trace; it can be diffed and replayed without a database server. The recorder writes through a temporary file before replacing the target.

**Trade-off:** Parsing whole documents costs more than indexed queries. There is no simultaneous-writer protocol, large-trace pagination, retention scheme, or version migration beyond rejecting unsupported versions.

**Evidence:** `tests/test_recorder.py` validates recording, JSON roundtrips, sequence validation, and failures.

## 2. Call interception instead of OpenTelemetry as the replay engine

**Decision:** Keep a small gateway interface (`llm_call`, `tool_call`, `decision`) that wraps the one demo agent.

**Why:** Observability spans can describe execution, but deterministic replay requires replacing responses and checking requests in order. An OpenTelemetry exporter could consume the same events later.

**Trade-off:** Instrumentation is not portable across agent frameworks; this repository deliberately supports one agent and one execution contract.

**Evidence:** Strict replay rejects a mismatched LLM request and an unexpected extra tool call; see `tests/test_replayer.py`.

## 3. Recorded LLM decisions instead of live regeneration

**Decision:** A strict replay consumes the exact recorded LLM result without contacting a hosted model.

**Why:** This gives a testable claim: normalized decisions can match a specific recorded execution. Even with a zero temperature, remote model and infrastructure changes could affect behavior.

**Trade-off:** A recorded response says nothing about what the model would do under a new prompt or new tool error. The harness therefore rejects new LLM calls after injection, rather than guessing at counterfactual behavior.

**Evidence:** The benchmark measures identical decisions across N strict replays; results are generated in `RESULTS.md`.

## 4. Local deterministic tool fixtures after a fault

**Decision:** Validate the fault target against the original trace, substitute one complete tool response, and use explicit offline fixtures for newly created tool calls after that point.

**Why:** A retry or fallback may introduce a call that does not exist in the baseline. Quietly consuming unrelated recorded responses would make the replay misleading.

**Trade-off:** Only the supported fake catalog/cache routes have defined recovery behavior. There is no emulation of real HTTP timing, connection pools, rate limits, or nondeterministic side effects.

**Evidence:** `tests/test_fault_injector.py` verifies all three recovery paths and errors for invalid targets, event types, and replacement payloads. A bug-prone sequence assumption is guarded by the named test `test_fault_on_llm_event_reports_type_mismatch`.

## 5. Synchronous CLI and benchmark, not a web dashboard

**Decision:** Run everything in one process and show diffs and aggregate outcomes in text.

**Why:** It makes control flow inspectable and keeps the core MVP within a 14-day implementation budget.

**Trade-off:** No concurrency, fan-out tools, async tasks, live deployment, production security boundary, or trace search UI.

**With two additional weeks:** First add recorded branch fixtures and an explicit compatibility/migration policy; next cover asynchronous execution order and side-effect safety; then consider OpenTelemetry import/export. I would not add a dashboard before these tests.
