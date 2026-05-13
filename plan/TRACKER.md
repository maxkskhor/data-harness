# plan/ - Work tracker

Tracks the status of items from `PLAN_v2.md`, `PLAN_SDK.md`, `PLAN_v3.md`, `PLAN_v4.md`, `PLAN_v5.md`, `PLAN_TEACHING.md`, and `IDEAS.md`.
Update this file as work starts or completes.

## PLAN_v2.md

| # | Item | Status | Notes |
|---|------|--------|-------|
| 1 | Python 3.10+ support | done | verified on 3.10 and 3.11 |
| 2 | Additional provider adapters (OpenAI) | done | OpenAIAdapter with mocked tests; live smoke gated by OPENAI_API_KEY |
| 3 | SDK ergonomics / simple `Agent` builder | done | PLAN_SDK phases 1-5 complete |
| 4 | CI / GitHub Actions | done | push/PR matrix for Python 3.10, 3.11, 3.12 |
| 5 | Publish to PyPI | blocked | name/version available; release workflows added; blocked on TEST_PYPI_TOKEN/PYPI_TOKEN secrets and TestPyPI verification |

## PLAN_SDK.md

| Item | Status | Notes |
|------|--------|-------|
| SDK ergonomics historical plan | done | earlier teaching-first framing is superseded; `dataact` is now the full SDK/framework track |

## PLAN_v3.md

| # | Item | Status | Notes |
|---|------|--------|-------|
| 1 | Disk-backed session cache | done | hot/cold storage policy, transparent hydrate, metadata-only logs |
| 2 | Subagent cache-boundary edge cases | done | input value-copy policy + publish collision contract |
| 3 | Real demo dataset | done | advanced demo uses checked-in FRED UNRATE sample |

## PLAN_v4.md

| # | Item | Status | Notes |
|---|------|--------|-------|
| 1 | Real sandbox (container-level) | deferred | moved from PLAN_v3 |
| 2 | Async loop | done | `AsyncHarness`, `AsyncAgent`, `AsyncAgentSession` in loop.py / agent.py |
| 3 | Streaming responses | done | `run_stream`/`ask_stream` on `AsyncHarness` and `AsyncAgent`; provider `stream()` base in providers/base.py |

## PLAN_v5.md

| # | Item | Status | Notes |
|---|------|--------|-------|
| 1 | Typed run results | done | `RunResult`, `Usage`, `CacheStorageInfo` in `result.py`; `run_result()`/`ask_result()` on Harness, Agent, AgentSession, AsyncAgent, AsyncAgentSession |
| 2 | Shared turn record for logging and results | done | `TurnSummary` aggregated in loop; logger and RunResult share the same record |
| 3 | Tool annotations | done | `ToolAnnotations` on `ToolSpec`; built-in tools annotated; not leaked to providers |
| 4 | Session inspection | done | `AgentSession.id`, `AgentSession.last_result`, `AgentSession.turns`; run/session UUIDs in RunResult |
| 5 | Documentation and examples | planned | add inspection docs and `examples/inspect_run.py` |

## PLAN_TEACHING.md

| Item | Status | Notes |
|------|--------|-------|
| Create `learn-dataact` teaching repo | planned | defer until the full `dataact` SDK/framework stabilises |

## IDEAS.md

| Item | Status | Notes |
|------|--------|-------|
| DuckDB variant / sql_query tool | idea | not near-future roadmap scope |
