# plan/ - Work tracker

Tracks the status of items from `PLAN_v2.md`, `PLAN_SDK.md`, `PLAN_v3.md`, and `IDEAS.md`.
Update this file as work starts or completes.

## PLAN_v2.md

| # | Item | Status | Notes |
|---|------|--------|-------|
| 1 | Python 3.10+ support | not started | requires-python currently >=3.12 |
| 2 | Additional provider adapters (OpenAI) | not started | AnthropicAdapter only |
| 3 | SDK ergonomics / simple `Agent` builder | re-scoped draft | see PLAN_SDK.md |
| 4 | CI / GitHub Actions | not started | no CI today |
| 5 | Publish to PyPI | not started | blocked on items 1, 3 + 4 |

## PLAN_SDK.md

| Item | Status | Notes |
|------|--------|-------|
| SDK ergonomics teaching-scope draft | in progress | Phases 1-4 done: minimal `Agent`, `FakeAdapter`, connector builder, schema inference, planner and subagent enablement; Phase 5 next |

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
