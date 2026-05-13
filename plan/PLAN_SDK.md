# dataact - Historical SDK Ergonomics Plan

Status: completed historical plan; teaching-first framing is superseded.

This plan records the earlier teaching-oriented SDK pass that introduced `Agent`, `ConnectorBuilder`, `FakeAdapter`, schema inference, planner/subagent enablement, and the quick-start example.

The current direction has changed: `dataact` is now the full SDK/framework track. A separate `learn-dataact` repository will be created later to extract the teaching version after the SDK stabilises.

The old framing was:

> publish an installable reference implementation, not a full agent framework.

That framing is historical. Current work should follow `PLAN_v5.md` for the full SDK refactor and `PLAN_TEACHING.md` for the future teaching split.

The rest of this file is retained as implementation history. Any teaching-first
or "not a framework" language below is not current project guidance.

---

## 1. Core tension

The current `examples/advanced_wiring.py` is useful as a wiring diagram. It shows the real pieces:

- `Harness`
- `SessionCache`
- `ConnectorRegistry`
- `ToolSpec`
- `python_interpreter`
- `list_variables`
- planner tools and reminder hook
- subagent setup
- provider adapter
- JSONL run logging

That explicit wiring teaches the architecture, but it is too noisy as the first user experience. A reader trying to run the project sees setup mechanics before they understand the central ideas.

The risk is the opposite failure mode: if we hide everything behind a polished SDK, the repo stops being a good teaching artefact. The convenience layer would obscure the exact boundaries the posts are trying to explain.

So the goal is narrow:

> remove incidental setup noise while preserving the architecture as the main object of study.

---

## 2. Decision

Add a small convenience layer, but constrain it aggressively.

The high-level API may compose existing primitives:

- create the shared `SessionCache`
- add `python_interpreter`
- add `list_variables`
- manage `ConnectorRegistry`
- create `load_connectors`
- wrap connector outputs with cache-aware formatting
- optionally add planner tools and reminder hook
- optionally add subagent tool
- construct `Harness`

It must not become a second runtime. It must not replace the low-level API. It must not make the repo read like a framework pitch.

`Harness` remains the centre of the project. `Agent` is a teaching-friendly shortcut over `Harness`.

---

## 3. Complexity budget

This is the guardrail that keeps the project from drifting.

Allowed:

- one high-level class: `Agent`
- one connector helper: `ConnectorBuilder`
- one small schema helper if needed
- one testing helper: `FakeAdapter`
- one quick-start example
- one advanced wiring example that shows the explicit internals

Not allowed in this pass:

- plugin system
- lifecycle hooks
- global config files
- provider factory shortcuts such as `Agent.openai(...)`
- automatic provider cloning
- async
- streaming
- disk-backed cache
- production sandbox
- hidden tool discovery mechanisms beyond the existing connector registry
- a new runtime separate from `Harness`

Stop and reassess if the convenience layer needs more than two small modules or starts requiring its own architecture diagram.

---

## 4. API layers

The repo should present three explicit layers.

### Layer 1: `Agent`

The quick path. It removes boilerplate from examples.

```python
from data_harness import Agent
from data_harness.providers.anthropic import AnthropicAdapter

agent = Agent(
    adapter=AnthropicAdapter(model="claude-sonnet-4-6"),
    system="You are a data analyst.",
)

result = agent.run("Compute the mean of [1, 2, 3, 4, 5].")
print(result)
```

What it should do by default:

- create a `SessionCache`
- add `python_interpreter`
- add `list_variables`
- use the existing harness logging default without requiring `run_dir="./runs"` in quick-start code
- build and run a normal `Harness`

### Layer 2: `Harness` plus built-in tools

The teaching layer. This remains documented and should be shown immediately after the quick start as "what `Agent` composes for you".

### Layer 3: `ToolSpec`, adapters, and registry primitives

The extension layer. Users who want precise control can still build the wiring manually.

---

## 5. Constructor scope

Proposed first-pass constructor:

```python
class Agent:
    def __init__(
        self,
        adapter: ProviderAdapter,
        system: str,
        *,
        max_turns: int = 25,
        cache: SessionCache | None = None,
        run_dir: str | Path | None = None,
    ) -> None:
        ...
```

Intentional omissions:

- no provider-specific constructors
- no config object
- no plugin list
- no callback hooks
- no async options

`run_dir=None` means "use the existing `Harness` default". Logging remains on by default because JSONL logs are a core teaching invariant, not incidental SDK machinery. Beginner docs should not mention `run_dir`.

Expose teaching/debugging escape hatches:

```python
agent.cache
agent.last_harness
agent.last_run_file
agent.explain()
```

The cache is a core teaching concept, not a secret implementation detail. `last_harness` is better than `harness` because `Agent.run()` builds a fresh `Harness` for each call.

`Agent.run()` is one-shot, not a chat session. Each call starts a fresh message history, matching `Harness.run()` today. The docstring should say this directly.

`Agent.explain()` should return a short, readable low-level wiring sketch showing the equivalent `SessionCache`, built-in tools, connector registry, and `Harness(...)` construction. This method is part of the teaching surface, not a product feature.

---

## 6. Connector API

The connector API should teach the existing design:

1. create a named connector
2. add tools to it
3. let the model load the connector when needed

Primary form:

```python
market_data = agent.connector(
    "market_data",
    description="Market data tools.",
)

market_data.tool(
    fetch_ohlcv,
    description="Fetch OHLCV data for a ticker.",
)
```

This is clearer than:

```python
agent.add_connector("market_data", tools=[fetch_ohlcv_spec])
```

because the builder form maps directly onto the underlying concept: a connector is a named group of hidden tools.

`ConnectorBuilder.tool(...)` should return the original function. That keeps the door open for decorator syntax later without forcing decorator style into the first teaching path.

Decorator form can be deferred. It is pleasant, but it is not necessary for the first pass and may make the teaching path feel more magical.

Under the hood, the connector builder should create the same thing a reader would build manually:

```python
ToolSpec(
    name="market_data__fetch_ohlcv",
    description="Fetch OHLCV data for a ticker.",
    input_schema={...},
    handler=fetch_ohlcv,
    visible=False,
)
```

The docs should show this expansion.

---

## 7. Schema inference

Schema inference is useful, but it can easily become a framework feature.

First pass:

- infer only simple signatures
- reject unsupported signatures with a clear error
- allow explicit `input_schema` override

Supported annotations:

| Python annotation | JSON schema |
|---|---|
| `str` | `{"type": "string"}` |
| `int` | `{"type": "integer"}` |
| `float` | `{"type": "number"}` |
| `bool` | `{"type": "boolean"}` |
| `list[str]` | `{"type": "array", "items": {"type": "string"}}` |

Rules:

- parameters without defaults are required
- parameters with defaults are optional
- reject `*args` and `**kwargs`
- reject `dict`, `Any`, `Union[...]`, `Optional[...]`, custom classes, dataclasses, `datetime`, and nested collections in the first pass
- if inference fails, the error must include the literal string `pass input_schema=... to override`

Do not build a general Python-to-JSON-schema library.

---

## 8. Planner and subagents

Planner and subagents are important teaching features, but they should not be in the minimum quick path.

Planner:

```python
agent.enable_planner()
```

When enabled, this composes:

- `Planner`
- planner tool specs
- `planner.reminder_hook`

Subagents:

```python
agent.enable_subagents(
    adapter_factory=lambda: AnthropicAdapter(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
    )
)
```

When enabled, this composes:

- `make_subagent_spec`
- parent cache
- base parent tools excluding recursive `subagent`
- connector tools rebuilt fresh for the subagent
- the same run directory policy as parent

Subagents require an explicit adapter factory. Do not auto-clone adapters.

Subagents do not inherit planner state or planner reminder hooks by default. They are fresh workers: input state crosses only through `input_handles`, and output handles return only through `publish_created`. If planner support inside subagents is ever needed, add it explicitly later.

---

## 9. Run lifecycle

`Agent.run()` should build fresh runtime tool specs for each run.

Reason: connector visibility mutates during a run. A second run should not accidentally inherit a connector that was loaded in the first run.

Lifecycle:

1. User registers connector definitions on `Agent`.
2. `Agent` stores those definitions immutably: connector name, connector description, function, tool description, optional explicit schema.
3. `run()` builds a fresh `ConnectorRegistry`.
4. `run()` builds fresh `ToolSpec` instances from the stored definitions.
5. Connector tools start hidden.
6. `load_connectors` flips visibility during that run.
7. The next `run()` starts clean.

Do not implement this as in-place visibility resets on long-lived `ToolSpec` objects. That will leak as soon as caller code holds a reference to a spec. Fresh registry plus fresh specs per call is the contract.

`Agent.run()` remains one-shot. It resets message history on every call because the underlying `Harness.run()` does that today. This is correct for the teaching reference, but docs should say it plainly so users do not expect a chat session.

---

## 10. Examples and docs

The docs should make the teaching structure explicit.

Recommended examples:

```text
examples/
  quickstart.py          # Agent, minimal path
  advanced_wiring.py     # current explicit demo style
```

README flow:

1. Quick start with `Agent`.
2. Short note: "`Agent` is only a convenience composition layer."
3. Show the lower-level pieces it composes.
4. Link to advanced wiring example.
5. Keep the blog-post framing as the primary motivation.

Keep `examples/advanced_wiring.py` in its explicit wiring style. The advanced wiring example should remain because it is the best teaching artefact for the architecture.

---

## 11. Proposed files

Keep the implementation small:

```text
dataact/
  agent.py      # Agent and ConnectorBuilder
  schema.py     # small signature-to-schema helper, only if needed
  testing.py    # FakeAdapter for docs and tests
```

Avoid a `dataact/sdk/` package for now. A nested SDK package makes the project feel more like a product framework than a compact reference implementation.

Export only the top-level convenience class:

```python
from data_harness import Agent
```

Keep existing low-level imports working.

---

## 12. Implementation phases

### Phase 1: minimal `Agent`

- Compose cache, interpreter, variables tool, and `Harness`.
- Keep `run_dir` optional and absent from examples.
- Keep logging on through the existing `Harness` default.
- Add `agent.explain()` as a teaching/debugging method.
- Add `agent.last_harness` and `agent.last_run_file` as inspection escape hatches.
- Publish `dataact.testing.FakeAdapter` for tests and runnable docs.
- Document that `run()` is one-shot, not a chat session.
- Add tests using `FakeAdapter`.

### Phase 2: connector builder

- Add `agent.connector(name, description=...)`.
- Add `ConnectorBuilder.tool(function, description=..., input_schema=None)`.
- Make `ConnectorBuilder.tool(...)` return the original function.
- Generate hidden prefixed `ToolSpec` objects.
- Store immutable connector definitions on the agent.
- Build a fresh `ConnectorRegistry` and fresh `ToolSpec` instances per `run()`.
- Preserve progressive disclosure via `load_connectors`.
- Show manual expansion in docs.

### Phase 3: optional planner

- Add `enable_planner()`.
- Register planner reminders internally.

### Phase 4: optional subagents

- Add `enable_subagents(adapter_factory=...)`.
- Keep adapter factory explicit.
- Prevent recursive subagent exposure.
- Do not inherit planner state or planner reminder hooks by default.

### Phase 5: docs and packaging readiness

- Rewrite README quick start.
- Keep `examples/advanced_wiring.py` as the explicit wiring example.
- Keep the advanced wiring example explicit rather than simplifying it.
- Add a minimal connector example.
- Confirm the package is described as an installable reference implementation.

---

## 13. Test plan

Unit tests:

- `Agent` composes a runnable `Harness`.
- `run_dir` is optional.
- logging still uses the existing `Harness` default when `run_dir` is omitted.
- `run()` is one-shot and resets message history between calls.
- `agent.explain()` returns a readable low-level wiring sketch.
- `agent.last_harness` points to the most recent harness after a run.
- `dataact.testing.FakeAdapter` can drive examples without live API calls.
- default tools include `python_interpreter` and `list_variables`.
- connector tools are hidden before `load_connectors`.
- connector tools become visible only inside the current run.
- connector return values use cache-aware formatting.
- repeated `run()` calls build fresh connector specs and reset connector visibility.
- schema inference supports only the documented cases.
- unsupported signatures produce clear errors containing `pass input_schema=... to override`.
- planner is absent by default and present after `enable_planner()`.
- subagent is absent by default and present after `enable_subagents()`.
- subagents do not inherit planner reminder hooks by default.

Regression tests:

- existing low-level `Harness` tests still pass.
- existing `ConnectorRegistry` behaviour remains understandable.
- no provider adapter mutation rules change.

Docs tests:

- README quick-start snippet can be executed with a fake adapter.
- advanced wiring example still demonstrates the explicit architecture.

---

## 14. Acceptance criteria

This work is successful only if all of the following are true:

- A new reader can run a useful example quickly.
- The README still makes clear that the repo is a teaching/reference implementation.
- `Agent` can be explained as a thin composition layer in a few bullets.
- `Harness` remains the central implementation.
- The advanced explicit wiring path remains visible.
- No plugin/config/lifecycle framework emerges.
- Packaging can be described honestly as "installable reference implementation", not "production SDK".

If any of these stop being true, cut scope rather than adding abstraction.

---

## 15. Open decisions

1. Should the first pass include connector schema inference?
   Recommendation: yes, but only the small documented subset.

2. Should the decorator connector form be included?
   Recommendation: no for the first pass. Start with the direct builder form because it is easier to teach.

3. Should planner default to enabled?
   Recommendation: no. Keep it opt-in.

4. Should subagents appear in the quick start?
   Recommendation: no. They belong in the advanced example.

5. Should packaging remain in v2?
   Recommendation: yes, but only after this plan lands and only as an installable reference implementation.
