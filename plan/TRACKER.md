# plan/ - Work tracker

Tracks the status of items from `PLAN_v2.md`, `PLAN_SDK.md`, `PLAN_v3.md`, and `IDEAS.md`.
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
| SDK ergonomics teaching-scope draft | done | `Agent`, `FakeAdapter`, connector builder, schema inference, planner/subagent enablement, docs and examples complete |

## PLAN_v3.md

| # | Item | Status | Notes |
|---|------|--------|-------|
| 1 | Real sandbox (container-level) | not started | moved from v2 |
| 2 | Async loop | not started | moved from v2 |
| 3 | Streaming responses | not started | moved from v2 |
| 4 | Disk-backed session cache | not started | moved from v2; hot/cold storage policy needed |
| 5 | Subagent cache-boundary edge cases | not started | reference-copy leak + publish collision contract |
| 6 | Real demo dataset | not started | moved from v2; README post links already done |

## IDEAS.md

| Item | Status | Notes |
|------|--------|-------|
| DuckDB variant / sql_query tool | idea | not near-future roadmap scope |
