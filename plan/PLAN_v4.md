# dataact — Deferred Runtime Work (v4 roadmap)

These items are useful, but they were intentionally deferred until the core runtime had stronger state, subagent, and demo coverage. They make the framework more production-like or integration-friendly. They should stay in `dataact`, not in the future `learn-dataact` teaching repo.

---

## 1. Real sandbox (container-level)

**Status: indefinitely deferred.**

`PythonInterpreter` uses AST checks + restricted builtins as a lightweight guard. A container-level sandbox is a significant infrastructure addition with non-trivial serialisation boundary requirements. It will not be prioritised until a concrete production use case drives the need.

When the time comes:
- Cache handles must still be injectable as locals (serialise to JSON on the boundary).
- `save()` helper must write back into the parent `SessionCache`.
- stdout/stderr must be captured and returned as the tool result.

Options to evaluate then: `subprocess` + `seccomp`/`seatbelt`, Docker/Podman sidecar, or `pyodide` (WASM).

---

## 2. Async loop

**Status: implemented.**

`AsyncHarness` in `loop.py` awaits provider calls and tool handlers.

- `AsyncProviderAdapter` in `providers/base.py` is the async ABC.
- Sync tool handlers are wrapped with `asyncio.to_thread`; async handlers are awaited directly.
- `AsyncHarness` keeps the sync `Harness` untouched — they are independent classes.
- `AsyncAgent` and `AsyncAgentSession` in `agent.py` wrap `AsyncHarness` at the convenience layer.
- `FakeAsyncAdapter` in `testing.py` supports async unit tests without a provider key.

---

## 3. Streaming responses

**Status: implemented.**

`AsyncProviderAdapter.stream(system, messages, tools, *, on_chunk)` delivers text tokens
via an async callback. The harness bridges the callback to an `AsyncGenerator[str, None]`
using an `asyncio.Queue`.

- `AsyncAnthropicAdapter` in `providers/anthropic.py` uses `client.messages.stream()` for
  real token streaming. Tool-use turns are handled internally; only final-answer text reaches
  the caller.
- `AsyncOpenAIAdapter` uses the default base-class implementation (full chat, single chunk).
  Real OpenAI streaming requires accumulating fragmented delta tool-call fields — deferred.
- `AsyncHarness.run_stream()` and `ask_stream()` are `AsyncGenerator[str, None]`.
- `AsyncAgent.run_stream()` and `AsyncAgentSession.ask_stream()` expose the same interface.
- The JSONL logger records fully assembled messages, not individual chunks.

Public usage::

    async for chunk in agent.run_stream("summarise this dataset"):
        print(chunk, end="", flush=True)
