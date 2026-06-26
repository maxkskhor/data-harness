# Quickstart

## Install

```bash
pip install data-harness          # core
pip install "data-harness[all]"   # + openai, charts, duckdb, sqlalchemy, notebook, eval
```

Set a provider key — `OPENROUTER_API_KEY` (one key, many providers),
`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or `DEEPSEEK_API_KEY`.

---

## `ask()` — one line

```python
import pandas as pd
from data_harness import ask

df = pd.read_csv("sales.csv")
result = ask(df, "What was total revenue, and which month was highest?")

print(result.text)    # the written answer
print(result.value)   # the structured value the model computed via answer()
result.charts         # any charts it rendered (renders inline in a notebook)
```

`ask` resolves a provider from the environment, loads `df` into a `SessionCache`
as a handle, runs the agent, and returns a [`RunResult`](../api/agent.md#data_harness.RunResult).
Pass `model=` to choose explicitly — a `provider/model` id routes via OpenRouter:

```python
ask(df, "plot revenue by month", model="deepseek/deepseek-v4-flash")
```

`data` can also be a `{name: frame}` mapping (multiple handles → joins), a file
path, or a list of paths.

---

## `Chat` — multi-turn

Keeps one message history and cache alive so follow-ups build on earlier turns:

```python
from data_harness import Chat

chat = Chat(df)
chat.ask("What was total revenue?")
chat.ask("Which month was highest?")   # remembers context
```

---

## `dh` — from the shell

Installed as `dh` (and `data-harness`):

```bash
dh "What was total revenue?" sales.csv
dh "Join these and find the top region" orders.csv customers.csv
cat sales.csv | dh "median order amount" --json
```

---

## What happens under the hood

`ask`/`Chat` are thin layers over `Agent`, which builds a `Harness` with:

- a **`python_interpreter`** tool — the model's only execution surface (no bash);
- a **`list_variables`** tool — inspect cache handles without dumping raw data;
- optionally a **`sql_query`** tool when DuckDB is installed.

The model writes Python against the cache handles; large results stay in the
cache and come back as compact snapshots, never raw rows in the prompt.

---

## Inspecting the result

```python
result = ask(df, "Total revenue?")
result.text        # final text response
result.value       # structured answer (from answer(...))
result.charts      # list of ChartArtifact
result.turns       # provider turns used
result.usage       # Usage(input_tokens=..., output_tokens=...)
result.run_file    # path to the JSONL log
```

---

## Dropping down to `Agent` / `Harness`

For full control over tools, system prompt, and wiring:

```python
from data_harness import Agent
from data_harness.providers.anthropic import AnthropicAdapter

agent = Agent(adapter=AnthropicAdapter(model="claude-sonnet-4-6"),
              system="You are a data analyst.")
print(agent.run("Compute the mean of [1, 2, 3, 4, 5]."))
```

`Agent.from_dataframe(df)` preloads data and resolves a provider for you;
`Agent.enable_sql()`, `enable_cache()`, `execution="subprocess"`, and `on_code`
add SQL, the replay cache, the sandbox, and the approval gate. See
[Asking questions](asking.md) for those.

---

## Testing without an API key

```python
from data_harness import Agent
from data_harness.testing import FakeAdapter

adapter = FakeAdapter([FakeAdapter.text("The mean is 3.0.")])
agent = Agent(adapter=adapter, system="You are a data analyst.")
assert agent.run("What is the mean?") == "The mean is 3.0."
```

---

## Next steps

- [Asking questions](asking.md) — charts, SQL, semantic layer, production controls
- [Evaluation](evaluation.md) — measure quality and cost across models
- [Sessions](sessions.md) · [Connectors](connectors.md) · [Async & Streaming](async.md)
- [Architecture](design.md) — why the harness is designed this way
