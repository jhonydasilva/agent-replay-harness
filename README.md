> 🇺🇸 English | 🇧🇷 [Português](README.pt-BR.md)

# agent-replay-harness

LLM-powered agents are difficult to debug: the same prompt can produce different tool calls on subsequent runs. Observability traces tell us what happened, but a recorded trace alone is not an executable, deterministic reproduction of a failure. This small harness records one fake agent's interactions, replays recorded LLM/tool responses, and replaces a chosen tool response to exercise a fixed recovery policy.

![CI workflow configured; live status not verified](.github/assets/ci-badge.svg)

The badge means a CI workflow is present, **not** that remote GitHub Actions have passed. The local checks and measured results appear below. There is no required API key, database, external API, or paid dependency.

## Quickstart (two commands)

From a clean checkout of this repository, in the repository root (Python 3.11+ and GNU Make required):

```bash
python -m venv .venv
make setup && make demo
```

The setup step installs the project's development dependencies; it may access a package index. `make demo` and `make test` make **no network calls**. No preconfigured environment variables are needed. On Windows, use WSL or a POSIX shell with GNU Make for the documented commands.

The demo records a trace, strictly replays the checked-in baseline, injects retry/fallback/fail-fast faults, prints the first divergent decision for each, and shows a CLI trace summary. All fixtures are synthetic and local.

```text
record: outcome=success
replay: outcome=success; decisions_identical=True
inject retry: outcome=success; decisions_identical=False
inject fallback: outcome=success; decisions_identical=False
inject fail_fast: outcome=failure; decisions_identical=False
Local trace dashboard: 5 traces; 4 successes; 1 failure; 3 divergences
```

The lines above summarize the demo's expected behavior, not a live service. Use `make demo` to reproduce the actual output.

## Commands

```bash
make test
make lint
make bench

.venv/bin/python -m src.cli record --output runs/recorded.json
.venv/bin/python -m src.cli replay examples/traces/success.json --output runs/replayed.json
.venv/bin/python -m src.cli inject examples/traces/success.json \
  --fault examples/faults/retry.json --output runs/retry.json
.venv/bin/python -m src.cli report runs/
```

`make bench` generates [RESULTS.md](RESULTS.md) automatically. It runs 100 direct fake-agent recordings, 100 strict replays, and 100 fault-injected replays. The benchmark script is the only author of numeric results in `RESULTS.md`.

## Architecture

```text
                    CLI (record / replay / inject / report)
                                  |
                             DemoAgent
                                  |
                         LLM + Tool gateway
                                  |
                   +--------------+-------------+
                   |                            |
                Recorder                    Replayer
                   |                            |
               Trace JSON               Recorded responses
                   |                            |
                   |                     FaultInjector? ----> Local tool fixtures
                   |                            |
                   +------------ Comparator ---+
                                   |
                          Decision diff / CLI
                                   |
                      Benchmark -> RESULTS.md
```

The trace is versioned JSON with `schema_version`, `run_id`, `agent_version`, `started_at`, `input`, `mode`, and an ordered `events` array. Events are `llm.call`, `tool.call`, or `agent.decision`; each carries `seq` and `timestamp`. LLM/tool events contain both request and response; decisions contain an action and optional tool or outcome. The recorded baseline is [success.json](examples/traces/success.json), created by executing the fake agent rather than writing trace events by hand.

**Strict replay** checks request order and arguments against recorded interactions. Unexpected calls or changed decisions fail explicitly; it does not invoke an LLM or live service. **Injected replay** substitutes one recorded `tool.call` response and uses deterministic local tool fixtures for the new recovery branch. New LLM calls after the injection are unsupported and result in an error rather than a fabricated answer.

### Fault file contract

```json
{
  "target_seq": 3,
  "event_type": "tool.call",
  "replacement_response": {
    "status": "error",
    "error": {
      "code": "SERVICE_UNAVAILABLE",
      "message": "Simulated HTTP 503",
      "retryable": true
    }
  }
}
```

`target_seq` must be a positive integer and must exist in the baseline. The target must actually be a `tool.call`. An invalid target, event type, or response causes a clear error and a nonzero exit code. The example trace's tool event is **seq 3**. `retry.json`, `fallback.json`, and `fail_fast.json` cover retry after HTTP 503, fallback on timeout, and safe failure for an invalid response. Recovery decisions are made by Python rules, not by a newly sampled LLM.

## Definition of done for the MVP

A criterion passes only with execution evidence. Otherwise it is FAIL or NOT RUN; the benchmark measures criteria 3 and 4. Remote CI status is separate from local execution.

| # | Binary acceptance criterion | Measured by |
|---|---|---|
| 1 | From a clean Git clone, create a fresh `.venv` via `python -m venv .venv`; run `make setup && make demo` with no predefined environment variables, no network calls except dependency installation, and demo exit code 0. | Clean-clone command log |
| 2 | `make test` passes at least 12 tests including retry, fallback, and fail-fast. | pytest output |
| 3 | Strict replay of `success.json` reproduces 100% of normalized decisions; not assumed. | **#5** benchmark result |
| 4 | Injecting `retry.json` causes a deliberate, reported comparator divergence. | **#5** benchmark result + CLI demo |
| 5 | `benchmarks/run_benchmarks.py` measures replay, timing, and injections and automatically writes `RESULTS.md`. | Benchmark command output and generated file |

See [RESULTS.md](RESULTS.md) for local measurements and the implementation acceptance report accompanying this repository for the actual check outcomes. A failure in any acceptance criterion must be disclosed in the limitations below.

## Engineering decisions

1. **JSON rather than SQLite.** One trace is readable, diffable, and easy to include in a bug report. The cost is full-file I/O and no indexed query, concurrency, or large-trace handling.
2. **Synchronous replay rather than distributed playback.** Interaction order is explicit and testable without a scheduler. This leaves concurrency, timers, and races outside the reproducibility claim.
3. **Recorded LLM answers rather than live resampling.** A replay can reproduce the recorded tool decision exactly. It cannot predict how an actual LLM would respond to a new error; injected branches therefore use a fixed Python recovery policy and local fixtures.
4. **An executable adapter rather than direct OpenTelemetry integration.** Spans describe execution; this MVP needs request matching and response substitution at the call boundary. OpenTelemetry export could be added later without replacing the replay engine.

Full specification: [SPEC.md](SPEC.md). Further detail: [DECISIONS.md](DECISIONS.md). The day-by-day implementation plan is in [PLAN.md](PLAN.md); example interview questions are in [INTERVIEW.md](INTERVIEW.md).

## Limitations & what I'd do differently

- **This harness does not prove an agent is reliable in production.** It only demonstrates reproducibility for a captured execution within the supported boundary, and deterministic behavior of the defined recovery policy under controlled faults.
- It supports one agent, one initial LLM tool decision, one sequential tool call, and three hardcoded recovery conditions. It does not cover general agent frameworks, multi-turn LLM recovery, parallel tools, or live external services.
- A new LLM decision after a fault has no recorded answer; the harness rejects it. A next iteration would add explicitly recorded alternative branches and still distinguish them from live stochastic behavior.
- The recorder masks common secret **field names**, but cannot reliably remove secrets embedded in free-text prompts. Only synthetic inputs should be recorded with this MVP; do not feed it production traces containing personal data.
- The first specification draft targeted sequence 2 for an example fault. The actual recording puts an agent decision at sequence 2 and the tool response at sequence 3. The fault fixtures were corrected to seq 3, and validation rejects wrong targets instead of silently applying them.
- The timing baseline is a local mock, not a real LLM. Replay can be slower than the tiny fake-agent recording due to validation and comparison. These timings should not be generalized to hosted model latency.
- JSON lacks concurrency support, streaming, trace indexes, compression, and a formal cross-version migration system. Additional work should prioritize trace-format compatibility and broader failure fixtures, not a dashboard.
- **Note on criterion #1:** The initial validation failed in a sandbox without network access (DNS failure during dependency installation). The project was re-validated on a clean clone on Windows 11 with Python 3.14.6 and network access: `pip install -e ".[dev]"`, 32 tests passed, all CLI commands executed, and the benchmark regenerated `RESULTS.md`. The limitation was environmental, not a code defect.
- Ruff lint was **NOT RUN** here because it was not installed and the package index was inaccessible. Syntax compilation and pytest passed, but they are not substitutes for a Ruff check.
- No remote CI run has been verified here. The badge intentionally states only that the workflow has been configured; it should be replaced by a live workflow badge once the repository is published.

## Scope and licensing

This is a **14-day MVP**, with only local mocks and CLI-based reporting. Production integration, authentication, and polished UI are intentionally excluded. MIT licensed; see [LICENSE](LICENSE).
