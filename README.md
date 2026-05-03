# dataact

A minimal, framework-free, production-style ReAct agent loop in Python for data-intensive workflows.

## Architecture

The core innovation is the **handle/snapshot pattern**: large tool results (DataFrames, query outputs) live in a `SessionCache` and only a compact snapshot enters the message history. The model queries data through a sandboxed `python_interpreter`, never by reading raw bytes. This is combined with:

- **Progressive disclosure** — connector tools are hidden until explicitly loaded, keeping the tool list short
- **KV-cache discipline** — system prompt is prefix-stable; reminders and state go on the conversation suffix
- **Subagent isolation** — spawned agents get fresh adapters, fresh caches, and explicit state transfer via `input_handles`
- **Planner with nag reminders** — suffix-only nags escalate at 4 / 8 / 12 turns without progress

## Install

```bash
# requires Python 3.12+ and uv
uv sync
```

## Usage

```python
from dataact.loop import Harness
from dataact.providers.anthropic import AnthropicAdapter
from dataact.cache import SessionCache
from dataact.tools.interpreter import PythonInterpreter
from dataact.tools.variables import make_list_variables_spec

cache = SessionCache()
adapter = AnthropicAdapter(model="claude-sonnet-4-6")

harness = Harness(
    adapter=adapter,
    system="You are a data analyst.",
    tools=[
        PythonInterpreter.make_tool_spec(cache),
        make_list_variables_spec(cache),
    ],
    cache=cache,
)

result = harness.run("Compute 2 + 2 and print the result.")
print(result)
```

Run the full demo (requires `ANTHROPIC_API_KEY`):

```bash
uv run python examples/demo.py
```

Run tests:

```bash
uv run pytest tests/ -v
```

## Sandbox disclaimer

> The Python interpreter uses AST checks and restricted globals to reduce accidental misuse. It is not a container sandbox and should not be treated as safe for untrusted code.

## License

MIT
