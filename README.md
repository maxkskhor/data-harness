# data-harness

**A Python SDK for controlled data-agent workflows.**

No bash. Handle-based state. Logs that reconstruct what happened.

**[Documentation](https://maxkskhor.github.io/data-harness/)** · [PyPI](https://pypi.org/project/data-harness/) · [Changelog](#changelog)

---

Most agent frameworks hand the model a shell and call it a day. `data-harness` takes a different approach: the model executes Python only, large data objects live in a session cache and are exposed as named handles, and every turn is logged to JSONL. The result is a data agent that is auditable, reproducible, and safe enough to run in production.

---

## Install

```bash
pip install data-harness
```

OpenAI support:

```bash
pip install "data-harness[openai]"
```

Requires Python 3.10+.

---

## Quickstart

```python
from data_harness import Agent
from data_harness.providers.anthropic import AnthropicAdapter

agent = Agent(
    adapter=AnthropicAdapter(model="claude-sonnet-4-6"),
    system="You are a data analyst.",
)

print(agent.run("Compute the mean of [1, 2, 3, 4, 5]."))
```

Switch to OpenAI by changing only the adapter:

```python
from data_harness.providers.openai import OpenAIAdapter

agent = Agent(
    adapter=OpenAIAdapter(model="gpt-4o-mini"),
    system="You are a data analyst.",
)
```

---

## Multi-turn sessions

`run()` is one-shot. For follow-up questions over shared state, use a session:

```python
session = agent.session()
session.put("sales", df)  # pre-load a DataFrame into the cache

print(session.ask("What is the total revenue?"))
print(session.ask("Which product category was highest?"))
```

The session keeps one message history and one cache alive across all `ask()` calls.

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
```

---

## Running the tests

```bash
uv run python -m pytest tests/ -v
uv run python -m pytest tests/smoke_tests.py -m live -v  # requires OPENAI_API_KEY
```

---

## Sandbox disclaimer

The Python interpreter uses AST checks and restricted globals to reduce accidental misuse. It is **not** a container sandbox and should not be treated as safe for untrusted input.

---

## Changelog

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
