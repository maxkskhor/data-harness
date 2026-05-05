# dataact

*(data + ReAct — a ReAct agent harness built for data workflows)*

A minimal, transparent, data-native agent harness for Python — built without bash.

Most agent frameworks hand the model a shell and call it a day. `dataact` takes a different approach: the model operates entirely through a sandboxed Python interpreter, with data stored in a session cache and exposed as named handles. No bash. No framework magic. Just a loop you can read in an afternoon.

Built as an installable reference implementation for engineers who want to understand how a production-style harness actually works. It is not a polished SDK surface; the convenience API exists to remove setup noise while keeping the harness boundaries visible.

The design is covered in two posts:

- [Designing a ReAct Harness for Data Workflows Without Bash](https://maxkskhor.substack.com/p/designing-a-react-harness-for-data)
- [The Engineering Invariants Behind a Data-Native ReAct Harness](https://maxkskhor.substack.com/p/the-engineering-invariants-behind)

---

## Why no bash?

Giving an agent shell access is the path of least resistance, but it creates real problems in production: unpredictable side effects, security exposure, and behaviour that's hard to reproduce. `dataact` deliberately constrains the model to Python only — which turns out to be enough for most data workloads and forces cleaner tool design.

---

## Core design decisions

Each decision here is intentional. Understanding them is the point.

**Handle/snapshot pattern**
Large objects (DataFrames, arrays, query results) live in a `SessionCache`, not in message history. The model only sees a compact snapshot — shape, columns, a few sample rows. It accesses the data by writing Python against the handle name. This keeps context lean without hiding data from the model.

**Prefix-stable system prompt**
The system prompt never changes between turns. Reminders, state, and nags are appended to the conversation suffix. This is a KV-cache discipline: a stable prefix means the provider can cache it, which reduces latency and cost on long runs.

**Progressive connector disclosure**
Data connectors (databases, APIs, warehouses) are registered but hidden from the tool list until explicitly loaded. A shorter tool list means the model makes better routing decisions. Connectors are only visible when relevant.

**Subagent isolation**
Spawned subagents get a fresh adapter and a fresh cache. State is transferred explicitly via `input_handles`. No implicit shared state. This makes subagent behaviour reproducible and debuggable.

**Suffix-only nag reminders**
The planner escalates reminders at 4 / 8 / 12 turns without progress. These are always appended to the suffix, never inserted into the prefix, so the KV cache is never busted by reminder text.

**JSONL turn logging**
Every turn is logged to a `.jsonl` file from the start. Not bolted on later. Each line is a complete turn record including latency, token counts, and cache hit/miss. Reproducibility is a first-class concern.

---

## Install

```bash
# requires Python 3.12+ and uv
uv sync
```

## Quick start

```python
from dataact import Agent


def build_agent(adapter, system="You are a data analyst."):
    return Agent(adapter=adapter, system=system)
```

Run the minimal example with a live Anthropic adapter:

```bash
uv run python examples/quickstart.py
```

`examples/quickstart.py` requires `ANTHROPIC_API_KEY` when run as a script. Tests import `build_agent()` and drive it with `FakeAdapter`, so the example stays covered without token spend.

## Connector example

Connector helpers keep the quick path small while preserving progressive disclosure. Connector tools start hidden; the model must call `load_connectors` before it can use them.

```python
from dataact import Agent

agent = Agent(adapter=adapter, system="You are a data analyst.")

market_data = agent.connector(
    "market_data",
    description="Market data tools.",
)


def fetch_ohlcv(symbol: str) -> list[dict]:
    return [{"symbol": symbol, "close": 101.2}]


market_data.tool(
    fetch_ohlcv,
    description="Fetch OHLCV data for a ticker.",
)

result = agent.run("Load market_data and inspect AAPL.")
print(result)
```

## What `Agent` composes

`Agent` is a thin composition layer over the lower-level primitives:

- `Harness` owns the ReAct loop, messages, dispatch, reminders, and JSONL logging.
- `SessionCache` stores large values as handles plus compact snapshots.
- `python_interpreter` is the controlled execution surface; there is no bash tool.
- `list_variables` exposes cache handles without dumping raw payloads.
- `ConnectorRegistry` keeps connector tools hidden until loaded.
- `Planner` reminders and subagents are opt-in helpers, not a second runtime.

For the explicit wiring, read [examples/advanced_wiring.py](examples/advanced_wiring.py). It deliberately shows the moving parts that `Agent` composes.

Run the advanced example - it loads a synthetic OHLCV dataset, runs analysis, uses subagents and the planner (requires `ANTHROPIC_API_KEY`):

```bash
uv run python examples/advanced_wiring.py
```

Run tests:

```bash
uv run pytest tests/ -v
uv run pytest tests/ -m live -v  # requires ANTHROPIC_API_KEY
```

---

## Project structure

```
dataact/
  loop.py          # Harness: the core ReAct loop
  cache.py         # SessionCache: handle/snapshot storage
  providers/       # Normalised adapter interface (Anthropic implemented)
  tools/
    interpreter.py # Sandboxed Python executor
    connectors.py  # Progressive connector registry
    planner.py     # Plan/nag tool
    subagent.py    # Isolated subagent spawning
    variables.py   # list_variables tool
  types.py         # Shared types: Message, ToolSpec, ContentBlock
  logger.py        # JSONL turn logging
  observe.py       # Latency measurement
examples/
  quickstart.py        # Minimal Agent path
  advanced_wiring.py   # Explicit Harness wiring
```

---

## Sandbox disclaimer

The Python interpreter uses AST checks and restricted globals to reduce accidental misuse. It is not a container sandbox and should not be treated as safe for untrusted input.

---

## License

MIT
