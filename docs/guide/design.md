# Architecture

This page explains the core design decisions in `data-harness` and why they
exist. Understanding them makes the API surface predictable.

---

## No bash

Giving an agent shell access is the path of least resistance, but it creates
real problems in data workflows:

- **Unpredictable side effects** — shell commands can touch files, processes,
  and network resources in ways that are hard to audit.
- **Security exposure** — prompt injection or a confused model can run
  destructive commands.
- **Reproducibility** — shell state is implicit and hard to reconstruct from
  logs.

`data-harness` constrains the model to a Python interpreter only. Python is
expressive enough for all data work, and the interpreter can be given explicit
globals and have dangerous operations blocked.

---

## Handle/snapshot pattern

Large objects (DataFrames, arrays, query results) never appear in message
history. Instead:

1. The tool result calls `SessionCache.put(name, value)`.
2. `format_tool_output` returns a compact snapshot — shape, columns, a few
   sample rows — as the tool result string.
3. The model writes Python against the handle name (`sales_df`, `result_2`,
   etc.) to operate on the data.

This keeps context lean without hiding data from the model.

```
Tool result →  {"type": "dataframe", "shape": [1200, 5],
                "columns": ["date", "revenue", ...], "sample": [...]}

Model code  →  result = sales_df[sales_df.revenue > 1000].groupby("category").sum()
               save("top_categories", result)
```

---

## Prefix-stable system prompt

The system prompt is never mutated between turns. Only the conversation suffix
changes. This is a KV-cache discipline: a stable prefix means the provider
can cache it, reducing latency and cost on long runs with many turns.

Reminders, nags, and dynamic state updates are always appended to the suffix.
The `Harness` enforces this invariant — it has no API to modify the system
prompt after construction.

---

## Progressive connector disclosure

Connector tools start hidden (`visible=False`). The model must call
`load_connectors(connector_name="...")` before the tools for that connector
appear in its tool list.

A shorter tool list means the model makes better routing decisions. Loading
all 40 connectors upfront would overwhelm the tool selection at each turn.
The model loads only what it needs for the current task.

---

## Suffix-only reminders

The `Planner` escalates reminders when the model has not made progress for
several turns. These reminders are always appended to the conversation suffix
as `TextBlock` items. They are never inserted into the prefix.

This preserves the stable-prefix invariant and avoids invalidating the
provider's KV cache on every reminder injection.

---

## Subagent isolation

Spawned subagents get:

- A fresh `AsyncProviderAdapter` (or `ProviderAdapter`)
- A fresh message history (empty)
- A fresh `SessionCache`

Parent state crosses the boundary only through explicit `input_handles`.
The parent cache is not inherited. This makes subagent behaviour reproducible
and debuggable independently of the parent run.

Subagents cannot spawn further subagents — `SubagentRecursionError` is raised
if they try.

---

## JSONL turn logging

Every turn is logged to a `.jsonl` file from the start of the run, not bolted
on later. Each line is a complete turn record:

- The system prompt and message history
- The provider response
- Tool results
- Latency and token counts
- Cache storage metadata

The log is designed to reconstruct a run without dumping raw dataset payloads.
Cache handles are logged as snapshots, not raw values.

---

## Key invariants

These are design constraints, not incidental behaviour:

- The system prompt is byte-identical across turns.
- Adapters never mutate harness-owned state.
- Dynamic reminders are suffix-only.
- Tool-use messages are always followed by matching tool-result messages before
  the next assistant call.
- Raw large payloads stay in `SessionCache`; messages and logs receive
  snapshots only.
- Cache handles are valid Python identifiers.
- `python_interpreter` uses fresh locals per call.
- Subagents do not inherit parent cache implicitly.
- JSONL logs support run reconstruction without raw payload leakage.

Tests in `tests/` assert these invariants directly.
