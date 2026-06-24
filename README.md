# data-harness

**A Python SDK for controlled data-agent workflows.**

No bash. Handle-based state. Logs that reconstruct what happened.

**[Documentation](https://maxkskhor.github.io/data-harness/)** · [PyPI](https://pypi.org/project/data-harness/) · [Changelog](#changelog)

---

Most agent frameworks hand the model a shell and call it a day. `data-harness` takes a different approach: the model executes Python only, large data objects live in a session cache and are exposed as named handles, and every turn is logged to JSONL. The result is a data agent that is auditable, reproducible, and safe enough to run in production.

---

## Install

```bash
pip install data-harness          # core
pip install "data-harness[all]"   # + openai, charts, duckdb, sqlalchemy, notebook
```

Pick individual extras as needed: `[openai]`, `[viz]`, `[duckdb]`, `[sql]`, `[notebook]`. Requires Python 3.10+.

---

## Quickstart

Ask a question about a DataFrame in one line. `ask()` resolves a provider from your environment (`ANTHROPIC_API_KEY` or `OPENAI_API_KEY`), loads the data into the session cache, runs the agent, and returns a `RunResult`:

```python
import pandas as pd
from data_harness import ask

df = pd.read_csv("sales.csv")
result = ask(df, "What was total revenue, and which month was highest?")

print(result.text)      # the written answer
print(result.value)     # the structured result the model computed via answer()
result.charts           # any charts it rendered (notebook-friendly)
```

Pick a model explicitly (routes to the matching provider):

```python
ask(df, "plot revenue by month", model="gpt-4o-mini")
```

Or reach many providers through one key with [OpenRouter](https://openrouter.ai) — a `provider/model` id auto-routes there (great for cross-model testing). Set `OPENROUTER_API_KEY`:

```python
ask(df, "summarise the data", model="anthropic/claude-3.5-sonnet")  # via OpenRouter
ask(df, "summarise the data", model="google/gemini-2.0-flash-001")
ask(df, "summarise the data", model="deepseek/deepseek-chat")       # cheap
```

DeepSeek's own (very cheap) API is also supported directly — set `DEEPSEEK_API_KEY` and use a bare `model="deepseek-chat"`.

In a notebook, the returned `RunResult` renders prose, the computed value, and charts inline. There's also a `%%ask` magic (`%load_ext data_harness.notebook`).

---

## Multi-turn chat

```python
from data_harness import Chat

chat = Chat(df)
chat.ask("What was total revenue?")
chat.ask("Which month was highest?")   # remembers context
```

---

## Charts

matplotlib is available inside the interpreter. The model builds a figure and it is captured automatically as an artefact — the image bytes live on disk and never enter the message history or logs (only a path does):

```python
result = ask(df, "Plot revenue by region as a bar chart.")
result.charts[0]        # a ChartArtifact; renders inline in Jupyter
```

---

## SQL over your data

With DuckDB installed, `ask` exposes a `sql_query` tool that runs SQL directly against your DataFrames (results become new handles). Point it at a real database with a SQLAlchemy URL:

```python
ask(df, "Use SQL to get total revenue per region.")          # DuckDB, in-process

from data_harness import Agent
agent = Agent.from_dataframe(df).enable_sql(engine_url="postgresql://...")
agent.run("Top 5 customers by spend last quarter?")
```

---

## Production controls

```python
from data_harness import Agent, ExecutionCache

agent = (
    Agent.from_dataframe(df, model="gpt-4o-mini")
    .enable_cache(ExecutionCache("cache.json"))   # replay repeat questions, 0 tokens
)

# Run interpreter code in an isolated process (no network, CPU/time limits):
sandboxed = Agent.from_dataframe(df, execution="subprocess")

# Approve or block code before it runs ("show me the code"):
def approve(code: str) -> bool:
    print(code)
    return True

gated = Agent.from_dataframe(df, on_code=approve)
preview = Agent.from_dataframe(df, code_only=True)   # dry-run: never executes
```

- **Code-replay cache** — a repeat question over the same data *schema* replays the recorded code with no model call (zero turns, zero tokens), while staying correct when the data changes.
- **Subprocess sandbox** — interpreter code runs in a separate process with networking disabled and CPU/wall-clock limits; handles cross by value, results merge back.
- **Approval gate** — `on_code` sees every code block before execution and can block it; `code_only=True` returns the code without running it.

---

## Lower-level `Agent` and `Harness`

`ask`/`Chat` are conveniences over `Agent`, which is itself a thin layer over `Harness`. Drop down when you want full control:

```python
from data_harness import Agent
from data_harness.providers.anthropic import AnthropicAdapter

agent = Agent(adapter=AnthropicAdapter(model="claude-sonnet-4-6"), system="You are a data analyst.")
print(agent.run("Compute the mean of [1, 2, 3, 4, 5]."))
```

---

## Data connectors

Connectors group related tools and start *hidden* — the model loads them on demand. This keeps the tool list short and routing decisions sharp.

```python
market_data = agent.connector("market_data", description="Equity price data.")

@market_data.tool(description="Fetch daily OHLCV data for a ticker.")
def fetch_ohlcv(symbol: str) -> list[dict]:
    ...

agent.run("Load market_data and fetch AAPL prices.")
```

---

## Async and streaming

```python
from data_harness import AsyncAgent
from data_harness.providers.anthropic import AnthropicAdapter

agent = AsyncAgent(adapter=AnthropicAdapter(model="claude-sonnet-4-6"), system="...")

# Stream tokens as they arrive
async for event in agent.run_stream("Describe the dataset."):
    if event.type == "content_block_delta":
        from data_harness import TextDelta
        if isinstance(event.delta, TextDelta):
            print(event.delta.text, end="", flush=True)
```

---

## Why these constraints?

| Design decision | Why it matters |
|---|---|
| **Python only, no bash** | No shell side-effects, no destructive commands, reproducible runs |
| **Handle/snapshot pattern** | Large objects never bloat message history; the model still operates on them via Python |
| **Prefix-stable system prompt** | The provider's KV cache stays warm across turns, reducing latency and cost |
| **Progressive connector disclosure** | Fewer visible tools → better model routing decisions |
| **Subagent isolation** | Spawned subagents get a fresh cache; state crosses boundaries only through explicit handles |
| **JSONL logging from turn one** | Every run is reconstructable without raw data leaking into the log |

The design is covered in detail in a [three-part series](https://maxkskhor.substack.com/p/designing-a-react-harness-for-data) and in the [Architecture guide](https://maxkskhor.github.io/data-harness/guide/design/).

---

## What `Agent` composes

`Agent` is a thin layer over lower-level primitives you can wire directly for full control:

| Component | Role |
|---|---|
| `Harness` | The ReAct loop — messages, tool dispatch, reminders, JSONL logging |
| `SessionCache` | Handle-based store; keeps large objects out of message history |
| `ProviderAdapter` | Translates provider SDK responses into harness types |
| `python_interpreter` | The model's only execution surface |
| `ConnectorRegistry` | Hides connector tools until the model loads them |
| `Planner` | Opt-in nag reminders when progress stalls |
| `Subagent` | Isolated worker with explicit state transfer |

See [`examples/advanced_wiring.py`](examples/advanced_wiring.py) for explicit Harness wiring.

---

## Running the examples

```bash
# Minimal Agent example (requires ANTHROPIC_API_KEY)
uv run python examples/quickstart.py

# Full wiring with connectors, planner, and subagents (requires ANTHROPIC_API_KEY)
uv run python examples/advanced_wiring.py

# Live tour of ask()/charts/SQL on a cheap model (ANTHROPIC or OPENAI key)
uv run python examples/live_demo.py

# Code-replay cache benchmark (no API key, deterministic)
uv run python examples/cache_benchmark.py
```

See [`examples/demo.ipynb`](examples/demo.ipynb) for an executed notebook covering all the v0.5 features.

---

## Running the tests

```bash
uv run python -m pytest tests/ -v
uv run python -m pytest tests/smoke_tests.py -m live -v  # requires OPENROUTER_API_KEY
```

---

## Sandbox disclaimer

The Python interpreter uses AST checks and restricted globals to reduce accidental misuse. It is **not** a container sandbox and should not be treated as safe for untrusted input.

---

## Changelog

### 0.5.0
- **Entry points:** `ask(df, "...")` one-liner, `Chat`/`SmartFrame`, zero-config provider resolution, `Agent.from_dataframe` / `from_csv`, and a `%%ask` notebook magic
- **OpenRouter & DeepSeek:** `OpenRouterAdapter` + `OpenAIAdapter(base_url=...)`; `provider/model` ids (e.g. `anthropic/claude-3.5-sonnet`) auto-route to OpenRouter, `deepseek-*` ids to DeepSeek's direct API, with `OPENROUTER_API_KEY` / `DEEPSEEK_API_KEY` picked up automatically — one key for many providers
- **Charts:** matplotlib in the interpreter; open figures captured as `ChartArtifact` handles (bytes stay out of messages/logs); `RunResult.charts` + rich Jupyter display
- **Structured results:** `answer(value)` interpreter helper → `RunResult.value`
- **SQL:** `sql_query` tool (DuckDB in-process over cached frames, or a SQLAlchemy URL); `Agent.enable_sql`
- **Semantic layer:** per-handle column/units descriptions folded into snapshots (`cache.put(..., semantics=...)`, `cache.describe`)
- **Subprocess sandbox:** `execution="subprocess"` runs interpreter code in an isolated process (no network, CPU/time limits)
- **Approval gate:** `on_code` callback and `code_only` dry-run
- **Code-replay cache:** `Agent.enable_cache(...)` replays repeat questions with zero model calls
- New optional extras: `[viz]`, `[duckdb]`, `[sql]`, `[notebook]`, `[all]`

### 0.4.0
- `python_interpreter`: runtime errors now raise `PythonInterpreterError` so the harness marks `ToolResultBlock.is_error=True`
- `python_interpreter`: final-expression capture — bare expressions return their repr automatically (notebook-like behaviour)
- `python_interpreter`: `locals()` usage detected at AST level and returns a targeted error with `list_variables` guidance
- `python_interpreter`: improved empty-output message directs the model to `print(...)` or `save(name, value)`
- `python_interpreter`: strengthened tool description with explicit guidance on handle usage, stdout capture, fresh locals, and `save()`

### 0.3.0
- Streaming protocol: SSE event types, `stream_events()`, `AsyncAgent.run_stream()`

### 0.2.0
- Async support: `AsyncAgent`, `AsyncAgentSession`, `AsyncHarness`
- `AgentSession` for multi-turn conversations
- `RunResult` with token usage and cache state

### 0.1.0
- Initial release: `Agent`, `Harness`, `SessionCache`, `ProviderAdapter`

---

## License

MIT
