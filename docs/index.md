# data-harness

*data + ReAct — a controlled data-agent SDK for Python workflows.*

A data-native agent SDK for Python — built around controlled execution,
handle-based state, provider adapters, sessions, subagents, and
reconstructable runs.

Most agent frameworks hand the model a shell and call it a day.
`data-harness` takes a different approach: the model operates through a
constrained Python interpreter, with data stored in a session cache and
exposed as named handles. No bash. Explicit state. Logs that can reconstruct
what happened.

---

## Why no bash?

Giving an agent shell access is the path of least resistance, but it creates
real problems in production: unpredictable side effects, security exposure,
and behaviour that's hard to reproduce. `data-harness` deliberately constrains
the model to Python only — which turns out to be enough for most data
workloads and forces cleaner tool design.

---

## Core design decisions

**Handle/snapshot pattern** — Large objects (DataFrames, arrays, query results)
live in a `SessionCache`, not in message history. The model only sees a compact
snapshot — shape, columns, a few sample rows. It accesses the data by writing
Python against the handle name.

**Prefix-stable system prompt** — The system prompt never changes between
turns. Reminders, state, and nags are appended to the conversation suffix. A
stable prefix means the provider can cache it, which reduces latency and cost
on long runs.

**Progressive connector disclosure** — Data connectors (databases, APIs,
warehouses) are registered but hidden from the tool list until explicitly
loaded. A shorter tool list means the model makes better routing decisions.

**Subagent isolation** — Spawned subagents get a fresh adapter and a fresh
cache. State is transferred explicitly via `input_handles`. No implicit shared
state.

**JSONL turn logging** — Every turn is logged to a `.jsonl` file from the
start. Each line is a complete turn record including latency, token counts, and
cache hit/miss.

---

## Install

```bash
pip install data-harness
```

For OpenAI support:

```bash
pip install "data-harness[openai]"
```

---

## Quick example

```python
from data_harness import Agent
from data_harness.providers.anthropic import AnthropicAdapter

agent = Agent(
    adapter=AnthropicAdapter(model="claude-sonnet-4-6"),
    system="You are a data analyst.",
)
print(agent.run("Compute the mean of [1, 2, 3, 4, 5]."))
```

See the [Quickstart guide](guide/quickstart.md) to go further.

---

## Design series

The design behind `data-harness` is covered in a three-part series:

- [Designing a ReAct Harness for Data Workflows Without Bash](https://maxkskhor.substack.com/p/designing-a-react-harness-for-data)
- [How a Bash-Free Data Agent Remembers Its Work](https://maxkskhor.substack.com/p/how-a-bash-free-data-agent-remembers)
- [The Bugs Hidden Inside a Data Agent Harness](https://maxkskhor.substack.com/p/the-engineering-invariants-behind)

---

## License

MIT
