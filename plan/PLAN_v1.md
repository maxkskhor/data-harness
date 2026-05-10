# agent-harness — Implementation Plan

Historical note: this was the original minimal/reference-implementation plan.
The current `dataact` repo is now the full SDK/framework track. The future
`learn-dataact` repo will carry the small teaching version after the SDK
stabilises.

## Context

`agent-harness` is a portfolio repo for Max Khor that implements the architecture described in his Substack post *Harness Engineering for Data-Intensive Enterprise LLM Agents*. The repo is the public proof of the design — a minimal, framework-free, production-style ReAct agent loop in Python. The post explains the *why*; the code shows the *how*.

The core innovation: **handle/snapshot pattern** — large tool results live in a session cache, and only a snapshot enters the message history. The model queries data via a sandboxed `python_interpreter`, never by reading raw bytes. Combined with progressive disclosure for tool schemas and KV-cache discipline (prefix-stable, suffix-mutable), this makes long multi-turn agents over many data sources tractable.

## Architecture decisions (settled)

- Generic harness only — DuckDB variant deferred
- Sync, single-threaded loop
- Provider abstraction via thin adapter ABC; `AnthropicAdapter` as v1 reference
- Python 3.12, `uv`, `pyproject.toml`, MIT
- `loguru` console logs + JSONL conversation log
- `pytest` + `pytest-mock`; **TDD** — tests first
- Background validator: deferred. Streaming: deferred. Demo: synthetic.

---

## Architectural invariants (hard rules)

These are tested directly and must hold across all phases.

### Mutation boundary

- **Adapters never mutate harness-owned state.** Generic `system`, `messages`, `tools` passed into `chat()` come back unchanged. Provider-specific transforms (cache_control, schema reshaping) happen on adapter-local copies only.
- **The harness may intentionally mutate its own state.** `load_connectors()` flipping `ToolSpec.visible` or the planner updating its todo list are legitimate state changes. The invariant is about *adapter* side-effects, not banning state changes generally.

### Prefix-stable, suffix-mutable

- The `system` prompt is byte-identical across every provider call within a run.
- All reminders, nags, session state, and final-output instructions go on the conversation suffix. Specifically:
  - If the current user message is a `tool_result` message → append the reminder as an additional `TextBlock` inside the same user message.
  - If there is no current user message → create a new user text message containing the reminder.
- The system prompt never receives reminders.

### Tool-use ordering

- Every assistant message containing one or more `ToolUseBlock`s is followed before the next assistant call by one user message containing exactly one `ToolResultBlock` per `tool_use_id`.

### Snapshots, not payloads

- Raw connector/query data lands in `SessionCache` only. The message history sees snapshots.
- `list_variables` returns snapshots. `format_tool_output` decides whether to inline-or-cache. `python_interpreter` only ever returns small stdout/error strings.
- No full raw dataset ever appears in logged messages.
- **No automatic variable-state injection per turn** — variables are introspected on demand via `list_variables`.

### Tool handler binding

- `ToolSpec.handler` is an **already-bound callable**. The loop dispatches with `handler(**tool_input)` and does not know how dependencies were wired.
- Stateful tools are constructed through factories or callable classes that close over their dependencies (`SessionCache`, `Planner`, `ConnectorRegistry`, `adapter_factory`):
  ```python
  interpreter = PythonInterpreter(cache=session_cache)

  ToolSpec(
      name="python_interpreter",
      description="Run Python over cached handles.",
      input_schema={...},
      handler=interpreter.run,
  )
  ```
- This keeps the loop generic and lets tools depend on whatever they need.

### Subagent isolation and explicit state transfer

- A subagent's tool registry must not include `subagent`. Enforced in code.
- Subagents receive a fresh adapter (via factory), fresh message history, and fresh `SessionCache`.
- **No implicit parent state.** Cache handles cross the boundary only through explicit `input_handles` / `output_policy` parameters on the `subagent` tool (see Phase 4.4).

---

## Repository structure

```
agent-harness/
├── harness/
│   ├── __init__.py                  [exists — update Phase 0]
│   ├── types.py                     [Phase 0]   Message, blocks, ToolSpec, ToolResult
│   ├── serialize.py                 [Phase 0]   to_jsonable()
│   ├── exceptions.py                [Phase 0]   MaxTurnsExceeded, etc.
│   ├── format.py                    [Phase 0]   format_tool_output()
│   ├── loop.py                      [Phase 3]
│   ├── cache.py                     [Phase 2]
│   ├── observe.py                   [Phase 3]
│   ├── logger.py                    [Phase 1]
│   ├── providers/
│   │   ├── __init__.py              [exists]
│   │   ├── base.py                  [exists — replace ContentBlock w/ typed blocks in Phase 0]
│   │   └── anthropic.py             [Phase 1]
│   └── tools/
│       ├── __init__.py              [Phase 4]
│       ├── interpreter.py           [Phase 4]
│       ├── connectors.py            [Phase 4]
│       ├── planner.py               [Phase 4]
│       ├── subagent.py              [Phase 4]
│       └── variables.py             [Phase 4]
├── tests/
│   ├── __init__.py
│   ├── test_types.py                [Phase 0]
│   ├── test_serialize.py            [Phase 0]
│   ├── test_format.py               [Phase 0]
│   ├── test_providers.py            [Phase 1]
│   ├── test_logger.py               [Phase 1]
│   ├── test_cache.py                [Phase 2]
│   ├── test_loop.py                 [Phase 3]
│   ├── test_loop_reminders.py       [Phase 3, extended Phase 4]
│   ├── test_observe.py              [Phase 3]
│   ├── test_tool_interpreter.py     [Phase 4]
│   ├── test_tool_connectors.py      [Phase 4]
│   ├── test_tool_planner.py         [Phase 4]
│   ├── test_tool_subagent.py        [Phase 4]
│   ├── test_tool_variables.py       [Phase 4]
│   └── test_integration.py          [Phase 5]
├── examples/
│   └── demo.py                      [Phase 5]
├── runs/                            [runtime, gitignored]
├── pyproject.toml                   [exists — extend deps Phase 0]
├── .gitignore                       [Phase 0]
├── LICENSE                          [Phase 5]
└── README.md                        [Phase 5]
```

## What already exists

- `pyproject.toml` — Python 3.12, deps `anthropic`, `loguru`, dev `pytest`, `pytest-mock`
- `harness/__init__.py` — exports the existing types
- `harness/providers/base.py` — `StopReason`, `ContentBlock` (to be replaced), `NormalizedResponse`, `ProviderAdapter` ABC

---

## Phase 0 — Shared contracts

Lock canonical types every later phase consumes.

### Content block types

Replace the single generic `ContentBlock` with three typed dataclasses:

```python
@dataclass
class TextBlock:
    text: str

@dataclass
class ToolUseBlock:
    tool_use_id: str       # provider-supplied id
    tool_name: str
    tool_input: dict       # structured, not serialized

@dataclass
class ToolResultBlock:
    tool_use_id: str
    content: str           # serialized text (tool output)
    is_error: bool = False

ContentBlock = TextBlock | ToolUseBlock | ToolResultBlock
```

### Message

```python
@dataclass
class Message:
    role: Literal["user", "assistant"]
    content: list[ContentBlock]
```

User messages may contain `TextBlock` and/or `ToolResultBlock`. Assistant messages may contain `TextBlock` and/or `ToolUseBlock`.

#### Block serialization convention

Dataclasses don't carry a `type` field internally, but adapter conversion and JSONL logging emit one for unambiguous wire format:

```text
TextBlock        -> {"type": "text", "text": ...}
ToolUseBlock     -> {"type": "tool_use", "id": ..., "name": ..., "input": ...}
ToolResultBlock  -> {"type": "tool_result", "tool_use_id": ..., "content": ..., "is_error": ...}
```

The `to_jsonable()` helper produces this shape for blocks. The Anthropic adapter consumes the same shape when converting to provider payloads.

### ToolSpec

```python
@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict
    handler: Callable[..., Any] | None = None
    visible: bool = True

    def to_provider_dict(self) -> dict:
        # only name + description + input_schema
        ...
```

### Provider adapter signature

```python
class ProviderAdapter(ABC):
    @abstractmethod
    def chat(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec],
    ) -> NormalizedResponse: ...

    @abstractmethod
    def format_cache_control(self, obj: dict) -> dict: ...
```

The adapter copies and transforms inputs into provider payloads. It must not mutate the arguments.

### Exceptions

```python
class MaxTurnsExceeded(RuntimeError):
    def __init__(self, turns: int, last_response: "NormalizedResponse | None" = None):
        ...

class ToolNotFoundError(KeyError): ...
class SubagentRecursionError(RuntimeError): ...
```

### `to_jsonable()`

Recursive, never raises. Handles dataclasses, Enum, Exception, datetime, DataFrame (snapshot fallback), unknown → `repr()`.

### `format_tool_output()`

Shared formatter that decides inline-vs-cache:

```python
def format_tool_output(
    value: Any,
    cache: SessionCache,
    preferred_name: str | None = None,
) -> str: ...
```

Decision matrix:

| input | behavior |
|---|---|
| short str / scalar | inline |
| short dict/list (e.g. ≤ N items, ≤ M chars JSON) | inline JSON-safe repr |
| long str | truncate head/tail; optionally cache |
| large dict/list | cache raw, return `"Saved as `<handle>`"` + snapshot |
| DataFrame / ndarray / table-like | always cache, return handle + snapshot |
| Exception | friendly error string, `is_error=True` upstream |
| unknown object | `repr()` truncated, or cache if `preferred_name` provided |

Handle names are valid Python identifiers (the agent uses them as variable names in `python_interpreter`). On collision, auto-suffix and report the actual name in the returned string.

### TDD order for Phase 0

1. `tests/test_types.py`:
   - `TextBlock`, `ToolUseBlock`, `ToolResultBlock` round-trip through `to_jsonable()`
   - `Message.role` rejects invalid roles
   - `ToolSpec.to_provider_dict()` excludes `handler` and `visible`
   - `ProviderAdapter.chat()` signature exists with the right param names

2. `harness/types.py` — write the dataclasses above. Update `harness/providers/base.py` to use `TextBlock | ToolUseBlock | ToolResultBlock` in `NormalizedResponse.content`. Update `chat()` signature.

3. `tests/test_serialize.py`:
   - Dataclass, Enum, Exception, datetime, DataFrame, nested, None, unknown object

4. `harness/serialize.py` — `to_jsonable()`.

5. `harness/format.py` — `format_tool_output()` skeleton with the inline-vs-cache decision logic. **Cache-dependent tests deferred to Phase 2** (after `SessionCache` exists). In Phase 0 the function is implemented and only its inline-path branches (short string, short dict/list, scalar, exception) are unit-tested without touching a cache.

6. `tests/test_format.py` (Phase 0 portion): inline branches only — short string, short dict, scalar, exception → friendly error string. Cache-path tests added in Phase 2.

7. `harness/exceptions.py`.

8. Extend `pyproject.toml` with `pandas` and `numpy` (snapshots and interpreter need them). Add `.gitignore`.

9. Update `harness/__init__.py` exports.

**Verification:** `uv run pytest tests/test_types.py tests/test_serialize.py tests/test_format.py -v` — green. `uv sync` succeeds.

---

## Phase 1 — Anthropic adapter + logging

### TDD order

1. `tests/test_providers.py`:
   - `StopReason` enum values
   - `format_cache_control()` returns annotated **copy** (input unmodified)
   - `chat()` with mocked `anthropic.Anthropic`:
     - `NormalizedResponse` correct for stop reason, content blocks, token counts (incl. cache read/write)
     - All four stop-reason mappings
   - **Adapter input immutability:** record hashes of the `system` string, `messages` list (deep), `tools` list — assert unchanged after `chat()` returns
   - `cache_control` annotation appears in the *Anthropic-bound* payload only (mock's recorded call args), not on harness-side objects

2. `harness/providers/anthropic.py`:
   - `AnthropicAdapter(ProviderAdapter)` — `__init__(model, max_tokens=8096)`, instantiates `anthropic.Anthropic()`
   - `chat()`: deep-copies inputs, applies `cache_control` to system + last user message on the copy, converts harness `Message`/`ToolSpec` to Anthropic dicts, calls `client.messages.create()`, normalizes response into typed `TextBlock` / `ToolUseBlock` blocks
   - `format_cache_control()` returns dict copy with `{"cache_control": {"type": "ephemeral"}}`
   - Stop-reason mapping: `end_turn`/`tool_use`/`max_tokens`/`stop_sequence` → `StopReason`

3. `tests/test_logger.py`:
   - `setup_logger()` creates `./runs/<ISO-timestamp>.jsonl`
   - `log_turn()` appends a parseable JSON line with all expected keys
   - DataFrames in messages don't crash logging (use `to_jsonable`)
   - **System logging:** turn 1 contains both `system` (full text) and `system_hash`; turns ≥ 2 contain only `system_hash`
   - `system_hash` is byte-identical across all turns of a run

4. `harness/logger.py`:
   - `setup_logger(run_dir="./runs") -> str` — timestamped JSONL, configures loguru INFO sink
   - `log_turn(turn, system, messages, response, tool_results, latency_ms, run_file)` — appends one JSON line per turn.
   - **System logging policy:**
     - The `system` prompt is passed to the provider on every model call but is **not** appended to the conversation history — it stays as a separate stable argument.
     - In JSONL: turn 1 contains both the full `system` text **and** the `system_hash`. Turns ≥ 2 contain `system_hash` only (no `system` field).
     - Tests assert `system_hash` is identical across all turns of a run.
   - JSONL line shape:
     ```json
     {"turn", "timestamp",
      "system": "<full text on turn 1 only, absent otherwise>",
      "system_hash": "<sha256 every turn>",
      "messages", "response_content", "stop_reason", "tool_results",
      "metrics": {"input_tokens", "output_tokens",
                  "cache_read_tokens", "cache_write_tokens", "latency_ms"}}
     ```
     All values via `to_jsonable()`.

**Verification:** `uv run pytest tests/test_providers.py tests/test_logger.py -v` — green.

---

## Phase 2 — Session cache + handle/snapshot

### TDD order

1. `tests/test_cache.py`:
   - `put()`/`get()` round-trip; `put()` returns the resolved handle name
   - Valid Python identifier accepted; invalid name rejected (e.g. `"123foo"`, `"my-name"`)
   - **Auto-suffix on collision:** `put("sales", df1)` → `"sales"`; `put("sales", df2)` → `"sales_2"`. Both retrievable.
   - **Explicit overwrite:** `put("sales", df3, overwrite=True)` replaces `"sales"`, no suffix
   - `snapshot(handle)` for: DataFrame (schema, shape, sample rows), list (length, sample), dict (keys, sample), scalar (value), ndarray (shape, dtype, sample)
   - `list_handles()` returns mapping of handle → snapshot
   - `SessionCache(sample_size=N)` is configurable; default 5
   - Large DataFrame snapshot uses configured `sample_size`, not the full data

2. `harness/cache.py`:
   - `SessionCache(sample_size: int = 5)` with `put`, `get`, `snapshot`, `list_handles`
   - `put` returns the resolved handle name (after any suffixing)
   - Snapshot dispatcher by `isinstance` (DataFrame → ndarray → list → dict → scalar)

3. **Extend `tests/test_format.py`** with cache-path tests (these were deferred from Phase 0):
   - Large dict → cached, returns `"Saved as <handle>"` + snapshot string
   - DataFrame → always cached regardless of size, returns handle + snapshot
   - Collision → returned string contains actual suffixed handle name (e.g. `market_data_2`)
   - `preferred_name=None` → format chooses a default name; cache contains it
   - Inline branches still pass (do not regress)

**Verification:** `uv run pytest tests/test_cache.py tests/test_format.py -v` — green. Sanity: cache 10k-row DataFrame, snapshot is small.

---

## Phase 3 — Loop + observability + reminder hook

### TDD order

1. `tests/test_observe.py`:
   - `TurnMetrics` populated correctly
   - `time_block()` measures elapsed ms

2. `harness/observe.py`:
   - `TurnMetrics` dataclass
   - `time_block()` context manager

3. `tests/test_loop.py` — core loop:
   - Exits on `StopReason.END_TURN`, returns final assistant text
   - Hits `max_turns` → raises `MaxTurnsExceeded(turns, last_response)`
   - Tool dispatch: `ToolUseBlock` → handler called → `ToolResultBlock` appended to user message → continue
   - Multi-turn flow with `FakeAdapter` (turn 1: tool_use; turn 2: end_turn)
   - JSONL has one line per turn
   - **Tool-use ordering:** every assistant `ToolUseBlock` is immediately followed by a user `ToolResultBlock` with the matching `tool_use_id`
   - Tool not found → `ToolResultBlock(is_error=True)`, loop continues
   - **System byte-stable:** record system at turn 0; assert identical bytes received by adapter on every subsequent call
   - **Adapter input immutability:** assert harness's stored `messages` list and `tools` list are not mutated by the adapter (object identity / deep equality)
   - **Legitimate harness mutation:** a tool that flips `ToolSpec.visible` is allowed and reflected in the next adapter call's tool list (test using a stub tool)
   - **No automatic variable-state injection:** putting a value in `SessionCache` does not append a system-state message in the next turn (only `list_variables` reveals cache contents)

4. `tests/test_loop_reminders.py` — suffix-only reminder mechanics:
   - **Max-turn final-output reminder:** before the final allowed provider call (turn `max_turns - 1`), a reminder TextBlock is appended to the user message
   - If current user message is a `tool_result` message → reminder appended as additional `TextBlock` in the same user message
   - If no current user message → a new user `Message` with a `TextBlock` is created containing the reminder
   - System prompt remains byte-identical across all turns
   - Reminder hooks are called in deterministic order

5. `harness/loop.py`:
   - `Harness` class:
     ```python
     class Harness:
         def __init__(
             self,
             adapter: ProviderAdapter,
             system: str,
             tools: list[ToolSpec],
             max_turns: int = 25,
             run_dir: str = "./runs",
             cache: SessionCache | None = None,
         ): ...
         def run(self, user_message: str) -> str: ...
         def register_reminder(self, hook: Callable[[int, int], str | None]) -> None:
             # hook(current_turn, max_turns) -> reminder text or None
             ...
     ```
   - State: `self._messages: list[Message]`, `self._cache: SessionCache`, `self._reminders: list[Callable]`
   - Adapter receives only `visible` tools, filtered each turn
   - **Reminder application** (before each provider call):
     - Collect non-None outputs from all reminder hooks plus the built-in max-turn reminder (active on turn `max_turns - 1`)
     - If reminders exist: locate the current user message (last in `_messages` if `role == "user"`), append `TextBlock(text=reminder)` to its content. If no current user message, create one.
   - Tool dispatch:
     - Look up `ToolSpec` by name → call `handler(**tool_input)` → wrap output via `format_tool_output(...)` into `ToolResultBlock`
     - Catch exceptions → `ToolResultBlock(is_error=True, content=repr(exc))`
     - Build a single user `Message` whose content is the list of `ToolResultBlock`s for this turn
   - Per-turn: `log_turn(...)`

**Verification:** `uv run pytest tests/test_loop.py tests/test_loop_reminders.py tests/test_observe.py -v` — green.

---

## Phase 4 — The five tools

Each tool ships as a `ToolSpec` with handler. After all five are in, extend loop tests to cover full-system behaviors.

### 4.1 `interpreter.py` — sandboxed Python exec

- Default allowlist: `{pandas, numpy, json, math, datetime, collections, itertools}`, configurable
- AST static check: reject imports outside allowlist, reject `exec`, `eval`, `__import__`, `open`, `__*__` dunder access
- **Fresh locals per call** — interpreter does NOT persist arbitrary Python locals across calls
- Locals injected each call:
  - All current cache handles by name (`market_data = cache.get("market_data")`)
  - A `save(name, value)` helper that delegates to `cache.put(name, value)` and returns the resolved handle name (so the agent sees suffixing)
- Cache object itself is **not** exposed; only the per-call locals + `save()`
- Capture stdout via `redirect_stdout`; return stdout + any error string

**Tests (`test_tool_interpreter.py`):**
- Allowed import passes; disallowed import rejected
- `eval`, `exec`, `__import__`, `open` rejected
- Stdout captured
- Cache handles available as locals (`market_data` accessible after caching as `"market_data"`)
- `save("avg", df)` stores in cache; collision auto-suffixes; the returned name reflects suffixing
- Locals do not persist between calls (variable created in call 1 is undefined in call 2)
- `cache` object not in locals
- Exception in user code → friendly error string, no harness crash

### 4.2 `connectors.py` — progressive disclosure

- `ConnectorRegistry`:
  - Directory: `{connector_name: one_line_description}` — always visible to model
  - Hidden tools: `dict[connector_name, list[ToolSpec]]` with `visible=False`
- `load_connectors(name)` handler: flips `visible=True` on all tools belonging to `name`, returns rich description
- Harness filters tools by `visible=True` before passing to adapter
- **Connector tools must use `format_tool_output` to cache large/structured returns** — they don't return raw DataFrames into the message stream

**Tests (`test_tool_connectors.py`):**
- Directory rendered into the description / `load_connectors` schema
- Pre-load: hidden tool names not present in adapter-bound tool list
- Post-load: hidden tools become visible; their handlers dispatchable
- Unknown connector → `ToolResultBlock(is_error=True)`
- A connector tool returning a 10k-row DataFrame stores in cache and returns only the snapshot string in the `ToolResultBlock` content
- The full DataFrame never appears in `_messages` or in JSONL

### 4.3 `planner.py` — todo + suffix-only nag

- `Planner` state: `[{id, text, status}]`, `_turns_since_update: int`
- Tool actions: `add(items)`, `update(id, status)`, `list()`
- Registers reminder hook with the harness:
  - Pending items exist and `_turns_since_update >= 4` → gentle nag
  - `>= 8` → firm
  - `>= 12` → urgent
  - Resets to 0 on any action
- Reminder is suffix-only (handled by harness reminder mechanism)

**Tests (`test_tool_planner.py`):**
- Add → list → update flow
- Threshold transitions (4 / 8 / 12)
- Reset on update
- No reminder when no pending items

### 4.4 `subagent.py` — clean-context spawn with explicit state transfer

#### Model-facing schema

```python
subagent(
    task: str,
    input_handles: list[str] | None = None,
    output_policy: Literal["text_only", "publish_created"] = "text_only",
)
```

- `task`: the natural-language instruction for the subagent
- `input_handles`: parent cache handle names to seed into the subagent's cache. The parent's raw values are **copied** into the subagent cache under the same handle names. Raw data never goes through the prompt.
- `output_policy`:
  - `"text_only"` (default): return only the subagent's final text
  - `"publish_created"`: copy handles **created during the subagent run** back into the parent cache using normal collision suffixing; include returned handle names + snapshots in the tool result

Only handles created during the subagent run are eligible for publishing back. Input handles copied in are not re-published unless the subagent explicitly transformed them into new named artifacts.

#### Construction

- Configured at construction with `adapter_factory: Callable[[], ProviderAdapter]` — fresh adapter per spawn
- Sub-harness gets:
  - `adapter_factory()` (fresh)
  - **Copies** of parent's `ToolSpec`s (by `dataclasses.replace`) with the `subagent` ToolSpec removed. The subagent must not be able to mutate parent tool registry by flipping `visible` or otherwise.
  - Fresh `SessionCache(sample_size=parent.sample_size)`
  - Fresh message history
  - **Explicit subagent system prompt** (see below)
- Hard check: constructing a sub-harness while the `subagent` tool is registered raises `SubagentRecursionError`

#### Subagent system prompt (explicit, not inherited)

The subagent system prompt is a fixed worker-style template owned by the `subagent` tool:

> You are a clean-context worker invoked by another agent.
>
> Your task: `{task}`
>
> Available input handles (already loaded into your cache): `{input_handles or "none"}`
>
> Use `python_interpreter` to inspect cached handles. Call `save(name, value)` for any computed artifact worth returning. You must produce final text summarizing your findings. If you save artifacts, mention what they contain and why they matter.

This is intentionally not the parent's system prompt. The subagent does not inherit project context, tone, or instructions beyond the worker role.

#### Tool result formatting

For `output_policy="text_only"`:

```text
Subagent final output:
<final text>
```

For `output_policy="publish_created"`:

```text
Subagent final output:
<final text>

Published outputs:
- sub_summary -> sub_summary_2
  Snapshot: {type: dataframe, schema: [...], shape: [...], sample: [...]}
- ...
```

Snapshots only — no raw data in the tool result string.

#### Edge cases

- `input_handles` referencing a handle missing from the parent cache → `ToolResultBlock(is_error=True)`, no subagent spawned
- Subagent run raises (max turns, etc.) → `ToolResultBlock(is_error=True)` containing the partial transcript / error summary; no handles published
- Subagent created no new handles under `publish_created` → "Published outputs: none"

#### Tests (`test_tool_subagent.py`)

- Sub-run completes and returns text (default `text_only`)
- Sub-harness's tool list excludes `subagent`
- `SubagentRecursionError` raised when constructing a sub-harness with `subagent` registered
- Sub-run uses a *different* adapter instance than parent (factory called once per spawn)
- Sub-run uses fresh `SessionCache` (parent's cache untouched)
- **No implicit parent state:** with `input_handles=None`, sub `SessionCache` is empty regardless of parent contents
- **`input_handles` copies only requested handles** by name into sub cache (not all)
- **Missing input handle:** `subagent(input_handles=["nonexistent"])` → `ToolResultBlock(is_error=True)`, parent cache unchanged
- Final text always returned to parent
- `text_only` does **not** publish created handles back (parent cache unchanged)
- `publish_created` copies only newly-created handles back; uses parent cache collision suffixing; published names reflect suffixing
- Published outputs section lists handle names + snapshots only (assert no raw data leaks)
- Input handles passed in are not re-published unless transformed into new handles
- **Tool spec isolation:** subagent flipping `visible` on a copied ToolSpec does not mutate the parent's ToolSpec instances

### 4.5 `variables.py` — list session cache

- `list_variables()` handler: returns formatted `cache.list_handles()` as a readable string
- Snapshots only — never raw data

**Tests (`test_tool_variables.py`):**
- Returns all handles with snapshots
- Empty cache → readable empty message
- 10k-row DataFrame in cache → result string contains snapshot rows only (size matches `sample_size`), not full data

### Loop-level reminder/integration tests (extends `test_loop_reminders.py`)

After all tools are in:

- Register a `Planner`. Run a scripted multi-turn flow with `FakeAdapter`. Skip planner updates for 4 turns. Assert:
  - Turn 5's user message contains the gentle nag string (as a `TextBlock` appended to the existing tool-result user message, or a new user message if none)
  - System prompt byte-identical to turn 0's
  - Updating the planner clears the nag from turn N+1's user message
- Run until 8 turns without update → assert firm wording
- `max_turns - 1` final-output reminder appears in the last user message before the final provider call

**Verification (end of Phase 4):** `uv run pytest tests/ -v` — all green.

---

## Phase 5 — Integration: demo + README + end-to-end

### TDD order

1. `tests/test_integration.py` — fully-mocked end-to-end with all five invariants asserted:
   - Scripted 4-5 turn flow with `FakeAdapter`:
     - Turn 1: `load_connectors("market_data")`
     - Turn 2: `python_interpreter` queries the loaded connector — full DataFrame stored in `SessionCache`
     - Turn 3: `list_variables` introspects cache
     - Turn 4: final text → loop exits
   - **Invariant assertions:**
     1. JSONL has 4 lines, each parseable
     2. `SessionCache` contains the full raw DataFrame from turn 2
     3. No message in the message history contains the full raw DataFrame (only snapshots)
     4. System prompt byte-identical across all 4 turns
     5. `cache_control` annotation seen in adapter-bound payloads only; harness's stored `_messages` and `_tools` carry no `cache_control` keys
   - Tool-use ordering: every `ToolUseBlock` paired with a `ToolResultBlock`
   - Subagent registered → its tools list excludes `subagent`; sub-spawn uses a fresh adapter (factory called); `publish_created` round-trip copies a new handle back into parent cache and the published handle name reflects parent-side collision suffixing
   - No automatic variable-state injection: putting a value in cache via interpreter does not auto-add a state message in the next turn
   - **System logging:** turn 1 JSONL line contains full `system`; turns 2-4 contain `system_hash` only; all four hashes match

2. `examples/demo.py`:
   - Wires `AnthropicAdapter`, registers all five tools, registers one mock connector ("market_data") with synthetic OHLCV DataFrame
   - Real Anthropic API (requires `ANTHROPIC_API_KEY`)
   - Prints final response and JSONL log path

3. `README.md` (tight):
   - One-line positioning
   - Short architecture summary
   - Install/usage snippet
   - **Sandbox disclaimer:**
     > The Python interpreter uses AST checks and restricted globals to reduce accidental misuse. It is not a container sandbox and should not be treated as safe for untrusted code.
   - Pointer to post (URL placeholder)
   - MIT note

4. `LICENSE` (MIT).

**Verification:** `uv run pytest tests/ -v` — green. Manual smoke: `uv run python examples/demo.py`. Inspect JSONL.

---

## Test strategy notes

- **`FakeAdapter(ProviderAdapter)`** for loop/tool tests: returns scripted `NormalizedResponse` objects, records every call (so we can assert byte-stability of system, no-mutation of generic state, and that `cache_control` only appears in adapter-internal payloads).
- **Anthropic SDK mocked** in `test_providers.py` only.
- **Real API** only in `examples/demo.py` and an opt-in integration test (skipped by default).
- **JSONL inspection:** parse line-by-line; assert structure and absence of full raw payloads.

## Out of scope (explicitly deferred)

- DuckDB variant
- Background validator
- Streaming
- Async loop
- Container-level sandboxing (documented limitation)
- Real demo dataset (synthetic only)
- Public Substack URL in README (placeholder)

## Implementation
Write down ongoing work status in TRACKER.md.
Test each phase before moving on to next phase.
