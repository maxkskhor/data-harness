# AGENTS.md / CLAUDE.md

This file provides guidance to coding agents working in this repository.

## What this is

`data-harness` (data + harness) is developing into a full SDK/framework for controlled data-agent workflows.

The repository began as a readable reference implementation of harness design. That teaching role is now being split out: after the full SDK stabilises, create a separate `learn-data-harness` repository that extracts the basic principles without async, production sandboxing, broader SDK ergonomics, or other framework-heavy concerns.

This repository is now the implementation and framework track. It should still make the core boundaries inspectable, but it no longer needs to stay artificially small for tutorial clarity.

The model operates through a constrained Python interpreter only — no bash tool. Large objects live in `SessionCache` and are exposed to the model as named handles with compact snapshots, never as raw blobs in message history.

## Current Direction

Build `data-harness` as the full SDK proper. Keep the foundational design visible, but allow the API surface to grow when it supports real data-agent workflows, debuggability, integration, or reproducibility.

When there is tension between SDK completeness and teaching simplicity, keep the full implementation in `data-harness` and record the distilled teaching version for the future `learn-data-harness` repo. Do not downgrade or avoid useful SDK features merely to keep this repository looking like a small tutorial.

The future `learn-data-harness` repo should be the clean teaching resource: basic ReAct loop, Python tool boundary, handle/snapshot cache, progressive tools, logging, and explicit subagent transfer. It should be created after `data-harness` has enough stable SDK shape that the guide will not immediately go stale.

Do not erase the core harness invariants. `data-harness` can become a framework, but it should remain explicit about execution, context, provider, state, subagent, and logging boundaries.

## Motivation

This project is motivated by data workflows where:

- unrestricted bash access is undesirable
- tool results can be large
- many data connectors may exist
- long-running conversations need disciplined context management
- debugging and reproducibility matter

The core design ideas remain:

- the ReAct loop should stay small and readable
- Python is the controlled execution surface for data work
- large tool outputs become handles plus snapshots
- connector schemas are progressively disclosed
- the system prompt stays prefix-stable
- reminders and dynamic state are appended to the conversation suffix
- subagent state transfer is explicit
- logs reconstruct runs without dumping raw datasets
- architectural invariants are tested directly

## Commands

```bash
uv sync
uv run pytest tests/ -v
uv run pytest tests/smoke_tests.py -v -m live
uv run pytest tests/test_loop.py::TestLoopBasic::test_exits_on_end_turn -v
uv run python examples/advanced_wiring.py
```

Live smoke tests require `OPENAI_API_KEY` and default to `gpt-4o-mini`; set
`DATA_HARNESS_OPENAI_SMOKE_MODEL` to override. The advanced demo requires
`ANTHROPIC_API_KEY`. Both may cost tokens.

## Architecture

The core loop is `Harness` in `loop.py`. It owns the message list, dispatches tools, applies reminder hooks, filters visible tools, and logs every turn to JSONL.

The harness never mutates the system prompt. Reminders, nags, final-turn warnings, tool results, and dynamic state belong in the conversation suffix.

`SessionCache` (`cache.py`) is shared state between the harness and tools. Tools store large objects by handle name. The model sees snapshots and can operate on handles through the Python interpreter.

`python_interpreter` injects cache handles as local variables and exposes `save(name, value)` for explicit persistence. It should not expose the cache object itself.

`ToolSpec` (`types.py`) carries the model-visible tool contract plus the already-bound handler callable. The loop dispatches with `handler(**tool_input)` and does not know how dependencies were wired.

Connectors (`tools/connectors.py`) are registered hidden and flipped visible on demand through `load_connectors`. This is the progressive disclosure pattern.

Provider adapters (`providers/base.py`) normalize external provider APIs into `NormalizedResponse`. Adapters copy and transform inputs; they must not mutate harness-owned `system`, `messages`, or `tools`.

Subagents (`tools/subagent.py`) get a fresh adapter, fresh message history, and fresh cache per spawn. Parent state crosses the boundary only through explicit `input_handles`, and created outputs return only through `publish_created`.

## Key invariants

These are design constraints, not incidental behavior:

- System prompt is byte-identical across turns.
- Adapters never mutate harness-owned state.
- Dynamic reminders are suffix-only.
- Tool-use messages are followed by matching tool-result messages before the next assistant call.
- Raw large payloads stay in `SessionCache`; messages and logs receive snapshots only.
- Cache handles are valid Python identifiers.
- `python_interpreter` uses fresh locals per call.
- Subagents do not inherit parent cache implicitly.
- Subagents cannot recursively register or call `subagent`.
- JSONL logs must support run reconstruction without raw payload leakage.

Tests should assert these invariants directly.

## Writing Context

This repo supports writing about harness and SDK engineering. The posts should be clear about the split: `data-harness` is the fuller implementation/framework track, while `learn-data-harness` is the planned teaching guide for the distilled principles.

There are two intended writing tracks:

1. Architecture: why this harness design exists.
   Topics: no bash, Python execution, progressive disclosure, handle/snapshot, prefix-stable suffix-mutable context, planner reminders, subagents, list_variables, failure modes.

2. Implementation invariants: the technical details that keep the design coherent.
   Topics: typed content blocks, adapter mutation boundary, tool-use ordering, inline-vs-cache formatting, handle naming, interpreter `save`, suffix-only reminders, explicit subagent state transfer, JSONL logs, invariant tests.

When updating README or docs, avoid claiming `data-harness` is still only a teaching/reference implementation. It is now developing into the full SDK/framework. If a simpler teaching resource is needed, point to the planned `learn-data-harness` split rather than forcing `data-harness` docs to stay beginner-oriented.

All writing in this repo uses British English spelling (e.g. behaviour, normalise, serialise, catalogue, artefact).

## Implementation Guidance

Prefer clarity over accidental abstraction, but do not impose the old "small enough for an afternoon" constraint on framework work.

Framework-style indirection is acceptable when it supports a real SDK responsibility: stable public API, provider integration, session/result metadata, reproducibility, observability, sandboxing, async execution, or safe extensibility. It is not acceptable when it hides state, weakens cache boundaries, or makes run reconstruction harder.

For SDK work, keep the public surface coherent and tested. It may grow beyond the original `Agent` convenience layer, but new APIs should map cleanly onto the underlying runtime concepts.

The high-level class is still `Agent`, and `Harness` remains the central implementation boundary unless a later plan explicitly replaces it.

The old strict SDK complexity budget is superseded. Use the current plan files to decide scope:

- `plan/PLAN_v4.md`: deferred runtime work such as real sandboxing, async, and streaming.
- `plan/PLAN_v5.md`: Claude-SDK-informed result/session/tool metadata refactor.
- `plan/PLAN_TEACHING.md`: future `learn-data-harness` teaching split after the SDK stabilises.

For connector convenience, store immutable connector definitions on `Agent` and build a fresh `ConnectorRegistry` plus fresh `ToolSpec` instances for every `run()`. Do not reset visibility on long-lived specs.

`Agent.run()` is one-shot, matching `Harness.run()`: it starts a fresh message history each call. Subagents should remain fresh workers and should not inherit planner state or planner reminder hooks by default.

The important boundaries are:

- Execution boundary: Python interpreter, not bash.
- Context boundary: snapshots, not raw payloads.
- Provider boundary: adapters copy and transform; they do not mutate harness state.
- State boundary: handles are explicit and valid Python identifiers.
- Subagent boundary: no implicit parent state; input/output handles are explicit.
- Logging boundary: reconstruct behavior without dumping full datasets.

## Release checklist

Before merging any branch that will trigger a PyPI release:

1. Run `uv run ruff check data_harness tests` — must exit 0.
2. Run `uv run ruff format --check data_harness tests` — must exit 0.
3. Run `uv run pytest tests/ -m "not live"` — must exit 0.

The `release.yml` workflow runs all three steps before `uv build` and `uv publish`. A failure in any step blocks the publish. Fix lint and format issues locally before pushing release tags or triggering the workflow manually.
