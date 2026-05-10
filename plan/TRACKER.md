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
| 2 | Async loop | deferred | moved from PLAN_v3 |
| 3 | Streaming responses | deferred | moved from PLAN_v3 |

## PLAN_v5.md

| # | Item | Status | Notes |
|---|------|--------|-------|
| 1 | Typed run results | planned | preserve string APIs; add `RunResult` metadata path |
| 2 | Shared turn record for logging and results | planned | aggregate usage and tool metadata without parsing JSONL |
| 3 | Tool annotations | planned | metadata only; no permission framework |
| 4 | Session inspection | planned | session/run ids plus `last_result`, no resume/list API |
| 5 | Documentation and examples | planned | add inspection docs after API shape is implemented |

## PLAN_TEACHING.md

| Item | Status | Notes |
|------|--------|-------|
| Create `learn-dataact` teaching repo | planned | defer until the full `dataact` SDK/framework stabilises |

## IDEAS.md

| Item | Status | Notes |
|------|--------|-------|
| DuckDB variant / sql_query tool | idea | not near-future roadmap scope |
