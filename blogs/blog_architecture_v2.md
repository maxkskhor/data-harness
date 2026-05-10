# Designing a ReAct Harness for Data Workflows Without Bash

Most agent demos start with the same move: give the model a terminal.

It is easy to see why. Bash is general. It can inspect files, run scripts, install packages, call APIs, invoke command-line tools, and glue systems together. If the goal is to quickly demonstrate that an agent can "do things," shell access is the shortest path.

But for data workflows, especially in regulated environments, bash is often the wrong default abstraction.

The problem is not that shell access is useless. The problem is that it is too broad. It expands the audit surface, makes side effects harder to reason about, and gives the model access to capabilities that are unrelated to the task. If the work is data analysis, the agent usually does not need a terminal. It needs a controlled way to query, transform, inspect, and summarise data.

That leads to a different harness design.

Not "give the model every tool and hope it behaves," but:

- constrain execution to the right surface
- keep large data out of context
- reveal tool complexity only when needed
- preserve provider caching by keeping the prompt prefix stable
- make state legible without dumping it into the conversation

This post is about that harness design.

The intended reader is an engineer building internal data agents, analytics copilots, or other LLM systems where correctness, auditability, and context control matter more than open-ended autonomy. The specific domain matters less than the constraints: many data sources, large query results, long-running conversations, and users who expect numbers to be correct.

---

## The loop is not the hard part

A ReAct loop is simple. Call the model. If it asks for a tool, run the tool. Feed the result back. Repeat until the model returns a final answer or a maximum turn count is reached. That control flow can fit on a screen.

The hard part is everything around it: what tools the model sees, what is allowed to enter message history, where large data lives, how the model refers to state across turns, what changes between provider calls, and how a bad answer can be reconstructed after the fact.

Those are harness questions. A useful data-agent harness should be judged less by how much autonomy it gives the model and more by how carefully it controls execution, context, and state.

---

## Why Python, not bash, and not a tool sprawl

A model analysing a dataset needs to filter rows, join tables, compute aggregates, inspect schemas, and maybe call a controlled connector. It does not need arbitrary file-system access, package installation, or process management. Every extra capability becomes part of the safety and debugging surface — a failed bash run is hard to reconstruct because the model could have read the wrong file, relied on a non-reproducible local command, changed the environment, or followed an injected instruction in some command output.

A Python interpreter is narrower and more inspectable. Imports can be allowlisted, dangerous builtins blocked, code AST-checked before execution, stdout captured into the tool result, and tracebacks returned as text. When something goes wrong, the failure is a structured tool result, not an opaque shell exit code. There is also a fit argument: most data work is already Python — DataFrames, NumPy arrays, datetime handling, basic statistics — and aligning the harness with the workflow it is meant to support beats forcing the model through shell idioms.

The claim is not that Python is secure. AST checks and a restricted globals dictionary are not a sandbox; if the model is adversarial or the data source is untrusted, the execution boundary needs process or container isolation. But that is easier to reason about when the interface is still Python-shaped rather than shell-shaped.

The other common alternative is a sprawl of narrow tools: `query_database`, `filter_rows`, `join_tables`, `calculate_metric`. This looks tidy at first, but data work is compositional. The model ends up chaining many small calls, adding latency and tool-result clutter at every step. A small fixed tool set is easier to validate than a Python surface, but data work becomes awkward when every composition has to be encoded as a separate call. The interpreter has to be policy-controlled either way; the choice is whether composition lives in tool chains or in code.

In the design I use, the minimum useful tool surface is small:

- `python_interpreter` for computation over cached data
- `load_connectors` for revealing data-source tools on demand
- `planner` for tracking multi-step work
- `subagent` for isolated exploratory work
- `list_variables` for inspecting the session cache

That is enough to build useful behaviour without handing the model a shell.

---

## The connector problem: too many schemas

Data workflows usually involve many possible sources.

An internal data agent might need sales data, telemetry, CRM records, billing, inventory, support tickets, and reporting tables. If every schema is injected upfront, the model starts the task surrounded by noise — and the larger problem is routing. Long tool lists make source selection harder; similar connector names compete; slightly stale descriptions can pull the model toward the wrong source. Token cost and latency get worse too.

The fix is progressive disclosure.

At startup, the model sees a lightweight catalogue of available connectors: names and one-line descriptions. It knows what exists, but it does not see every schema. The catalogue lives inside the description of a single `load_connectors` tool, so the initial surface is one tool, not dozens:

```
Load a data connector to make its tools available.
Available connectors:
- sales: customer orders, line items, refunds, and currency tables
- telemetry: device events, error logs, and uptime metrics
- crm: customer records, contact history, and account hierarchy
- billing: invoices, payments, and subscription state
```

When the model decides a source is relevant, it calls `load_connectors`. That call flips the visibility of the connector's tools from hidden to visible, and the response describes what was loaded:

```
Loaded connector 'sales'.
Description: customer orders, line items, refunds, and currency tables
Available tools: ['sales__get_orders', 'sales__get_refunds', 'sales__lookup_customer']
```

This turns tool exposure into a demand-driven process. The model pays for the connector surface only when it needs it. A simple task loads one connector. A more complex task can load several. The harness avoids spending context on tools that are not relevant to the current job.

This is similar to progressive disclosure in user interfaces, but the mechanism is different. In a UI, the concern is mostly human attention. In an LLM harness, overloading the model with schemas increases token cost, increases latency, and can degrade routing accuracy.

---

## Tool results are not context

A query can return 100,000 rows. A connector can return a table with dozens of columns. A model cannot usefully reason over 100,000 rows pasted directly into message history. Dumping raw data into context wastes tokens, pushes the original user intent further back in the conversation, and encourages the model to "read" data instead of query it.

The better pattern is: tool results become handles, not payloads. When a tool returns a large object, the harness stores the raw value in a session cache. The conversation receives only a snapshot — the handle name, the data type, shape, columns, and a small sample. The model sees enough to decide what to do next, but not enough to treat the conversation as the data store. When it needs to compute something, it calls the Python interpreter against the handle.

The handle is part of the model-facing interface. It is the key in the cache, and it is the variable name injected into the interpreter. That means handles have to be valid Python identifiers, suffixed predictably on collision, and treated as immutable references — derivations are persisted under new handles, not by mutating in place.

The cache is where most of the engineering judgement in this harness lives — handle naming, snapshot dispatch, immutability, proliferation, eviction, disk-backed spillover, subagent transfer. I cover that design in a follow-up post on the session cache.

The shorter version: the model does not need to read the data. It needs to query the data. That is how human analysts work — inspect the schema, sample a few rows, run queries. The handle/snapshot pattern gives the model the same workflow.

---

## Prefix-stable, suffix-mutable

Most LLM providers support some form of prompt caching. If the prefix of the prompt is byte-identical across calls, the provider can reuse cached computation. In long conversations, this matters for cost and latency.

A common mistake is to put dynamic state into the system prompt — a "current session variables" section that updates whenever the cache changes, or planner reminders inserted at the top of the role description. That mutates the prompt prefix on every turn and prompt caching stops working.

The rule is simple: the system prompt should be static. Dynamic state — tool result snapshots, planner reminders, final-turn warnings — belongs in the conversation suffix, appended near the current turn.

The mechanics — typed content blocks, the suffix-only reminder pattern, planner staleness escalation, and the discipline that keeps provider adapters from mutating harness state — sit in a separate post on engineering invariants.

---

## Subagents need explicit state transfer

Subagents are useful because they isolate work. A main agent can delegate exploratory analysis to a clean-context worker, get back a summary, and avoid polluting the main conversation with every intermediate step.

But subagents create a state problem. If a subagent silently inherits the parent's cache, tools, and planner state, it is not really clean-context — it is a second loop sharing implicit state. The cleaner design is explicit state transfer: a subagent gets a fresh adapter, fresh message history, fresh session cache, and no recursive `subagent` tool. If the parent wants the subagent to see existing data, it passes named input handles into that fresh cache instead of sharing the parent cache wholesale. Any artefacts the subagent creates can be published back as new handles. Raw data never crosses through the prompt.

The exact boundary mechanics — how input handles are copied or isolated, collision suffixing for published handles, the recursion block — are covered in the cache and invariants posts.

---

## Where this design still breaks

This design removes several common failure modes, but it does not make agents magically reliable.

*Connector discovery can fail.* Progressive disclosure depends on the first-layer connector catalogue. If a connector description is vague, stale, or uses different terminology than the user, the agent may never load the right source. It may then produce a plausible answer from the wrong data.

*Progressive disclosure is path-dependent.* Once the agent loads a connector and finds something plausible, it may anchor on it. A better source may exist, but the agent has stopped searching. The order in which sources are discovered can shape the whole investigation.

*Context compaction can lose intent.* Long sessions eventually require summarisation or compaction. Summaries are lossy. A constraint from an earlier user message can disappear, and the agent may drift without realising it.

*Planner compliance is behavioural, not guaranteed.* Reminders improve the chance that the agent updates its plan, but they do not prove task completion. The agent can mark items done without finishing them, or rephrase the plan in ways that quietly drop a constraint. The planner is a coordination aid, not an audit trail.

*Handles proliferate.* The immutability discipline accumulates near-duplicate frames over a long session. There is no built-in eviction policy, and choosing one is a real design question — covered in the cache post.

These are the details that determine whether the design remains coherent as it grows.

---

## What the design is really about

The point of this harness is not to make the agent unconstrained. It is to give the model the right constraints. A useful data-agent harness is less about orchestration and more about boundaries:

- execution boundary: Python, not bash
- context boundary: snapshots, not payloads
- state boundary: handles, not hidden globals
- prompt boundary: prefix-stable, suffix-mutable
- subagent boundary: explicit input and output handles

The loop is simple. The boundaries are the design.

I'm building these ideas in [`dataact`](https://github.com/maxkskhor/dataact). Two follow-up posts go deeper: one on the session cache (handles, snapshots, immutability, eviction, disk-backed spillover) and one on the engineering invariants (typed content blocks, adapter mutation boundary, suffix-only context, subagent isolation, invariant tests). `dataact` is now the fuller SDK/framework track; a separate `learn-dataact` repo will distil the teaching version once the framework surface stabilises.
