# dataact — Deferred Runtime Work (v4 roadmap)

These items are useful, but they were intentionally deferred until the core runtime had stronger state, subagent, and demo coverage. They make the framework more production-like or integration-friendly. They should stay in `dataact`, not in the future `learn-dataact` teaching repo.

---

## 1. Real sandbox (container-level)

**Current:** `PythonInterpreter` uses AST checks + restricted builtins. Not a real sandbox — documented limitation.

**Goal:** run model-generated code in an isolated subprocess or container so that malicious or runaway code cannot affect the host process.

Options:
- `subprocess` with `seccomp`/`AppArmor` on Linux; `seatbelt` on macOS.
- Docker/Podman sidecar with mounted tmpfs volume for data exchange.
- `pyodide` (WASM) for a dependency-free sandboxed interpreter.

Design constraints to preserve:
- Cache handles must still be injectable as locals (serialise to JSON on the boundary).
- `save()` helper must write back into the parent `SessionCache`.
- stdout/stderr must be captured and returned as the tool result.

---

## 2. Async loop

**Current:** sync, single-threaded `Harness`.

**Goal:** `AsyncHarness` that awaits the provider call and tool handlers.

Why it matters:
- Enables concurrent subagent spawns without threading.
- Unblocks FastAPI/asyncio integration for server-hosted agents.

Design notes:
- `ProviderAdapter.chat()` becomes `async def chat()`.
- `ToolSpec.handler` becomes an async callable, or sync handlers are wrapped with `asyncio.to_thread`.
- `Harness.run()` becomes `AsyncHarness.run()` as a coroutine.
- Keep the sync `Harness` as a thin wrapper around `asyncio.run(async_harness.run(...))`.

---

## 3. Streaming responses

**Current:** full-response polling only.

**Goal:** stream assistant tokens to the caller so a UI can display partial output.

Design notes:
- Anthropic SDK supports `stream=True`; the adapter needs to yield token chunks.
- `NormalizedResponse` becomes an async generator, or a sync generator for a sync path.
- Harness accumulates the stream internally for tool-use detection and yields text chunks to the caller through a callback or generator.
- JSONL logger records the final assembled message, not individual chunks.
