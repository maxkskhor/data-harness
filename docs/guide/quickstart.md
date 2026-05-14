# Quickstart

## Installation

```bash
pip install data-harness
```

For OpenAI support, install the optional extra:

```bash
pip install "data-harness[openai]"
```

---

## Your first agent

`Agent` needs a provider adapter. The adapter is the boundary between the
provider SDK and the harness — it translates Anthropic/OpenAI responses into
`data-harness`'s normalised `Message`, `ToolUseBlock`, and token-count types.

=== "Anthropic"

    ```python
    from data_harness import Agent
    from data_harness.providers.anthropic import AnthropicAdapter

    agent = Agent(
        adapter=AnthropicAdapter(model="claude-sonnet-4-6"),
        system="You are a data analyst.",
    )

    result = agent.run("Compute the mean of [1, 2, 3, 4, 5] and print it.")
    print(result)
    ```

=== "OpenAI"

    ```python
    from data_harness import Agent
    from data_harness.providers.openai import OpenAIAdapter

    agent = Agent(
        adapter=OpenAIAdapter(model="gpt-4o-mini"),
        system="You are a data analyst.",
    )

    result = agent.run("Compute the mean of [1, 2, 3, 4, 5] and print it.")
    print(result)
    ```

---

## What happens under the hood

`agent.run()` builds a fresh `Harness` with:

- A **`python_interpreter`** tool — the model's only execution surface.
  There is no bash tool.
- A **`list_variables`** tool — lets the model inspect what's in the cache
  without dumping raw data.

The model receives a Python REPL it can call freely. Results are stored in a
`SessionCache` and returned to the model as compact snapshots.

---

## Inspecting the result

`Agent.run()` returns the final text response as a string. For more detail —
token counts, cache state, log file path — use `run_result()` instead:

```python
result = agent.run_result("Compute the mean of [1, 2, 3, 4, 5].")

print(result.text)         # final text response
print(result.turns)        # number of provider turns used
print(result.usage)        # Usage(input_tokens=..., output_tokens=...)
print(result.run_file)     # path to the JSONL log
```

See [`RunResult`](../api/agent.md#data_harness.RunResult) for all fields.

---

## Testing without an API key

Use `FakeAdapter` from `data_harness.testing` to drive the agent in tests:

```python
from data_harness import Agent
from data_harness.testing import FakeAdapter

adapter = FakeAdapter(responses=["The mean is 3.0."])
agent = Agent(adapter=adapter, system="You are a data analyst.")

assert agent.run("What is the mean?") == "The mean is 3.0."
```

---

## Next steps

- [Sessions](sessions.md) — multi-turn conversations over shared state
- [Connectors](connectors.md) — progressive disclosure of data tools
- [Async & Streaming](async.md) — async execution and token streaming
- [Architecture](design.md) — why the harness is designed this way
