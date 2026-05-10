# dataact - Claude-SDK-Informed Framework Refactor

Status: draft plan for discussion.

This plan is separate from `PLAN_v4.md`. `PLAN_v4.md` is the older deferred
runtime roadmap for sandboxing, async, and streaming. This plan is about what
`dataact` can learn from the Claude Agent SDK now that `dataact` is the full
SDK/framework track rather than the teaching artefact.

The goal is narrow:

> expose the harness's existing run, session, tool, and telemetry boundaries
> more clearly, while growing the framework surface deliberately.

---

## 1. What to borrow

The Claude Agent SDK is useful less because of its full feature set, and more
because it names several boundaries explicitly:

- one-shot execution versus stateful conversation
- final result metadata, not just final text
- session identity and inspection
- structured tool metadata
- turn-level usage and error metadata
- clear separation between runtime control features and core message flow

`dataact` already has the important one-shot/session split:

- `Agent.run()` is one-shot and returns text.
- `Agent.session().ask(...)` keeps one `Harness`, message history, and cache.

That split should stay. The useful refactor is to make the outputs and metadata
around those paths first-class instead of forcing users to inspect private
fields or parse JSONL logs.

---

## 2. What not to borrow in this phase

Do not copy the whole Claude SDK surface in this refactor.

Out of scope for this plan:

- MCP server configuration
- plugin loading
- filesystem settings sources
- global permission systems
- lifecycle hook framework
- CLI session stores
- checkpointing / file rewind
- remote sessions
- cost estimates from provider pricing tables
- a second runtime beside `Harness`

These exist in Claude because Claude Code is a production coding-agent runtime
with Bash, file editing, permissions, resumable workspaces, and external tools.
`dataact` is becoming a data-agent SDK/framework. Its scope can grow, but that
growth should be sequenced through explicit plans rather than copied wholesale
from Claude.

The comparison should sharpen `dataact`'s boundaries while it expands into a
real framework.

---

## 3. Phase 1 - Typed run results

**Current:** `Harness.run()` and `Agent.run()` return only final text. Metrics
exist in JSONL logs, but callers do not get a typed result object.

**Goal:** add a first-class result path while preserving the current string API.

Add small result dataclasses, likely in a new `dataact/result.py` module:

- `Usage`
- `TurnSummary`
- `RunStatus`
- `RunResult`

Initial `RunResult` fields:

- `text: str`
- `status: Literal["success", "max_turns_exceeded", "error"]`
- `turns: int`
- `run_file: str | None`
- `stop_reason: StopReason | None`
- `usage: Usage`
- `cache_storage: dict[str, dict[str, str]]`
- `error: str | None`

API additions:

- `Harness.run_result(user_message: str) -> RunResult`
- `Harness.ask_result(user_message: str) -> RunResult`
- `Agent.run_result(user_message: str) -> RunResult`
- `AgentSession.ask_result(user_message: str) -> RunResult`

Compatibility rules:

- Keep `Harness.run()` returning `str`.
- Keep `Harness.ask()` returning `str`.
- Keep `Agent.run()` returning `str`.
- Keep `AgentSession.ask()` returning `str`.
- The existing string methods should become thin wrappers over the result
  methods.
- Existing `MaxTurnsExceeded` behaviour may remain on the string methods, but
  the result methods should return `status="max_turns_exceeded"` with partial
  metadata.

Tests:

- result path returns final text and aggregate usage
- string path still returns exactly the same text
- max-turns result path includes status and last metadata
- `run_file` is populated and points to the JSONL file
- no raw cached payloads appear in result metadata

---

## 4. Phase 2 - Shared turn record for logging and results

**Current:** `log_turn()` builds JSON records directly, while the loop separately
tracks enough state to return text.

**Goal:** make the loop produce a small typed turn summary that both the logger
and `RunResult` aggregation can use.

Add an internal `TurnRecord` or `TurnSummary` construction path that captures:

- turn number
- stop reason
- visible tool names
- tool use names
- tool result error count
- input/output/cache token counts
- latency
- cache storage metadata

Design constraints:

- Keep the JSONL log format readable.
- Continue logging full serialised messages for reconstruction.
- Continue omitting raw cached payloads.
- Do not require callers to parse JSONL to answer basic "what happened?"
  questions.

Tests:

- JSONL still has one line per turn
- aggregated result usage equals the sum of per-turn usage
- visible tool names reflect progressive connector disclosure
- tool errors are counted without changing the existing tool-result message flow

---

## 5. Phase 3 - Tool annotations

**Current:** `ToolSpec` exposes name, description, input schema, handler, and
visibility. It does not describe behavioural hints.

**Goal:** add lightweight metadata similar in spirit to Claude's tool
annotations, but do not build a permission system.

Add:

```python
@dataclass(frozen=True)
class ToolAnnotations:
    title: str | None = None
    read_only: bool | None = None
    cache_mutating: bool | None = None
    destructive: bool | None = None
    open_world: bool | None = None
```

Extend `ToolSpec`:

```python
annotations: ToolAnnotations | None = None
```

Initial annotations:

- `list_variables`: read-only, closed-world
- `python_interpreter`: cache-mutating, not open-world
- `load_connectors`: cache-neutral, changes visible tool surface
- connector tools: default open-world unknown unless caller supplies metadata
- `subagent`: cache-mutating only when `output_policy="publish_created"`

Use annotations for:

- documentation
- JSONL logging
- result summaries
- future permission discussions

Do not use annotations for enforcement in this phase.

Tests:

- annotations serialise in logs
- `ToolSpec.to_provider_dict()` does not leak annotation fields to providers
- built-in tools carry expected annotations
- connector builder can accept optional annotations without breaking schema
  inference

---

## 6. Phase 4 - Session inspection

**Current:** `AgentSession` keeps state, but callers mainly get `run_file`,
`cache`, and `harness`.

**Goal:** make sessions easier to inspect without adding persistence/resume.

Add:

- `Agent.last_result`
- `AgentSession.id`
- `AgentSession.last_result`
- `AgentSession.turns`

Possible shape:

- session id can be a generated UUID used in result metadata and JSONL records
- each one-shot `Agent.run_result()` also gets a run id
- subagent runs should log `parent_run_id` and `parent_tool_use_id` when
  available

Still out of scope:

- listing past sessions
- resuming sessions from disk
- renaming/tagging sessions
- external session stores

Tests:

- session id is stable across `ask_result()` calls
- `last_result` updates after each ask
- one-shot `Agent.run_result()` does not reuse an `AgentSession` id
- subagent metadata links child run to parent run without sharing cache state

---

## 7. Phase 5 - Documentation and examples

Update docs only after the result/session API is stable.

README changes:

- keep the quick start simple with `agent.run(...)`
- add a short "Inspecting a run" section using `agent.run_result(...)`
- show usage/turn count/run file, not a large framework-style config example
- keep `examples/advanced_wiring.py` as the explicit wiring artefact until
  `learn-dataact` exists

Example additions:

- `examples/inspect_run.py` using `FakeAdapter` or a cheap deterministic path
- optionally a live-provider snippet gated by environment variables

Tests:

- docs snippets remain importable
- deterministic example runs without provider keys

---

## 8. Deferred after this plan

These remain useful, but they should not be mixed into this refactor:

- async loop
- streaming responses
- real sandbox
- permission policy callbacks
- hook framework
- session resume/list/tag APIs
- structured output validation

The teaching-oriented version is also deferred. It belongs in `learn-dataact`,
not in this framework refactor.

The typed result and turn-record work should come first. Async and streaming
will be easier to design once the non-streaming loop has a clean event/result
shape.

---

## 9. Implementation order

Use TDD and keep the phases small.

1. Add failing tests for `RunResult` on `Harness`.
2. Implement result dataclasses and `Harness.run_result()`.
3. Wrap existing string APIs around result APIs.
4. Add `Agent.run_result()` and `AgentSession.ask_result()`.
5. Refactor turn logging to share `TurnSummary`.
6. Add tool annotations and logging support.
7. Add session/run ids and `last_result`.
8. Update README and examples.
9. Run targeted tests first, then full non-live tests.

Suggested verification:

```bash
uv run pytest tests/test_loop.py tests/test_agent.py tests/test_logger.py -v
uv run pytest tests/ -m "not live" -v
```
