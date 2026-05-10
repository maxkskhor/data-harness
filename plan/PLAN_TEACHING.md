# dataact - Teaching Split Plan

Status: planned after the full SDK/framework stabilises.

`dataact` is now the implementation and framework track. It should continue
building the full SDK proper first: result/session metadata, richer runtime
controls, sandboxing, async, streaming, provider ergonomics, and other
production-facing concerns as they become justified.

The teaching resource should be a separate repository:

> `learn-dataact`

Do not build `learn-dataact` yet. If it is created before the SDK shape
stabilises, it will either go stale quickly or force `dataact` to stay smaller
than it should.

---

## 1. Decision

Create `learn-dataact` after `dataact` has a reasonably stable framework API.

`learn-dataact` should extract the core principles from `dataact`, not mirror
the full implementation. It should be a teaching guide and small codebase for
understanding the harness design from first principles.

The split is:

- `dataact`: full SDK/framework, installable package, richer runtime and
  integration surface.
- `learn-dataact`: minimal teaching repo, linear lessons, deliberately small
  code, no framework-heavy features.

---

## 2. Why split

The earlier teaching-first framing is now constraining the main repo. Features
like typed run results, session inspection, async runtime, streaming, real
sandboxing, and richer SDK ergonomics are useful for the full framework, but
they make the first-principles story harder to follow.

Keeping both goals in one repo creates bad pressure:

- either `dataact` avoids useful framework features to stay tutorial-sized
- or the teaching path becomes noisy, dated, and hard to read

The separate repo lets each artefact do one job well.

---

## 3. Scope of `learn-dataact`

`learn-dataact` should cover the basic principles only:

- a small ReAct loop
- typed message/content blocks
- a constrained Python tool instead of Bash
- handle/snapshot state management
- compact tool-result formatting
- progressive tool disclosure
- provider adapter boundary, probably with a fake provider first
- JSONL logging and replay mindset
- explicit subagent input/output handles

It should avoid:

- async runtime
- streaming
- production sandboxing
- plugin systems
- permission frameworks
- MCP
- full provider matrix
- pricing/cost machinery
- persistent session stores
- package-publishing ceremony
- polished SDK convenience layers

---

## 4. Target repo shape

Possible structure:

```text
learn-dataact/
  README.md
  lessons/
    01_react_loop.md
    02_python_tool.md
    03_session_cache.md
    04_handle_snapshots.md
    05_progressive_tools.md
    06_logging_and_replay.md
    07_subagent_boundary.md
  src/
    loop.py
    types.py
    cache.py
    tools.py
    fake_provider.py
    logger.py
  examples/
    basic_analysis.py
    connector_disclosure.py
    subagent_boundary.py
  tests/
```

Keep the code small enough that a reader can move from lesson text to source
file without context switching across a framework.

---

## 5. Extraction principles

When creating `learn-dataact`:

- rewrite for explanation; do not mechanically copy `dataact`
- keep each concept in one short lesson and one small source file where
  possible
- use a fake provider by default so examples are deterministic
- add live-provider examples only as optional appendix material
- keep public API naming close enough to `dataact` that readers can graduate to
  the full repo
- explicitly state when `learn-dataact` simplifies or omits behaviour that
  exists in `dataact`

The teaching repo should explain the design pressure, not pretend the full SDK
does not exist.

---

## 6. Start criteria

Start `learn-dataact` only after these `dataact` pieces are stable enough:

- `Agent` and `AgentSession`
- core `Harness` loop
- `RunResult` / result metadata shape
- `ToolSpec` and tool annotations if they land
- provider adapter contract
- cache handle/snapshot contract
- subagent input/output boundary
- logging format

These do not need to be perfect, but they should be stable enough that the
teaching guide will not need immediate rewrites.

---

## 7. Documentation impact now

Current `dataact` docs should no longer claim this repo is primarily the
teaching artefact. They should say:

- `dataact` is the full SDK/framework track
- `learn-dataact` will be created later as the distilled teaching resource
- older teaching-oriented plans are historical

This avoids forcing current SDK plans to preserve the old "small reference
implementation" framing.

