# How a Bash-Free Data Agent Remembers Its Work

Handles and snapshots replace the working directory: raw data stays in cache, while the model sees compact names, shapes, and samples.

The previous post argued that a data agent should not get bash. Python is the right execution surface. Connector tools come and go through progressive disclosure. Tool results become handles plus snapshots, not raw payloads dumped into context.

That argument leaves a hole.

Without a shell-style working directory as a model-facing surface, the agent loses the filesystem-like workflow many autonomous agents rely on. It cannot casually `cat` a CSV, `mv` an intermediate result, or write a tmpfile to come back to in five turns. It cannot keep a working directory or rely on path names to remind itself what it has computed. Whatever state the agent needs across the run has to come from somewhere the harness controls.

That somewhere is the session cache.

In a shell-equipped agent the cache would be one tool among many. In a bash-free data agent, the cache is the agent's working memory. Most of the design judgement in this harness ends up living there: how values are named, how the model peeks at them, how derivations are tracked, when older state should be evicted, and how state crosses subagent boundaries.

This post is about that design.

---

## Handles are names

A handle is the model's equivalent of a filename.

When a tool returns a large object, the harness puts the raw value into the cache and gives it a name. The model sees that name in the tool result, refers to it in later reasoning, and uses it as a local variable when it calls the Python interpreter. That triple role is intentional. It is also why handles cannot be arbitrary strings — they have to be valid Python identifiers, short and descriptive, stable enough to reuse across turns.

Naming usually starts from the tool that produced the value. A connector named `sales` returning customer orders prefers `sales_orders`. An interpreter step that computes a weekly aggregate prefers `weekly_summary`. The cache decides the final name. If the preferred name is free, that is the name. If not, the cache suffixes:

```
first put: sales_orders
second put with same preferred name: sales_orders_2
third: sales_orders_3
```

The actual handle is reported in the tool result, never chosen silently. Silent overwrite would be one of the easiest ways to make a long session inconsistent: the model thinks `sales_orders` is one query, the cache has quietly replaced it with another, and an answer at turn 18 ends up wrong in a way that is hard to reconstruct from the transcript.

Identifier rules and explicit suffixing sound like small choices. In a data agent they are part of the usability of memory.

---

## Snapshots are `ls` and `head`

Without bash, the agent cannot open a file to look at it. The cache has to surface the equivalent automatically.

When something is cached, the harness emits a structured summary at the same time. The model sees:

```
Saved as `sales_orders`
Snapshot: {"type": "dataframe", "shape": [100000, 8],
           "columns": ["order_id", "customer_id", "order_date", "amount",
                       "currency", "region", "product_id", "status"],
           "sample": [{"order_id": "A001", "customer_id": "C42",
                       "order_date": "2024-01-02", "amount": 219.50,
                       ...}, ...]}
```

That is the equivalent of `ls -l` plus `head` for one cached value: type, shape, columns, a small sample. Enough to decide what to do next, not enough to treat the conversation as the data store.

A single shared formatter handles every tool's output. The centralisation matters more than any individual choice it makes:

- DataFrames and arrays are always cached, with type-specific snapshots
- short strings and scalars are inlined directly
- small dicts and lists are serialised inline
- long strings are cached with a head-and-tail summary
- exceptions become readable error strings
- unknown objects fall back to `repr()` truncated

The model learns one rule: small things are inlined, large or structured things become handles. If each connector wrote its own formatting, that rule would not hold, and the model would have to learn the quirks of every tool.

---

## Immutability is a discipline

The handle/snapshot contract assumes a cached value behaves like an immutable reference.

If the contract holds, the snapshot the model saw at cache time stays accurate. The handle keeps referring to the value it described. The transcript stays meaningful when read at turn 25 about something cached at turn 4.

The discipline is straightforward: if the agent transforms a cached frame, the right move is not to mutate the cache. It is to compute a new value and persist it under a new handle. The interpreter exposes a small `save(name, value)` helper for exactly that:

```python
# right — original handle still describes its snapshot
clean = sales_orders.dropna(subset=["amount"])
save("sales_orders_clean", clean)

# wrong — mutates the cached object in place
sales_orders.dropna(subset=["amount"], inplace=True)
```

The first form leaves `sales_orders` exactly as it was at cache time. The model can still reason about it. The second form silently changes the meaning of the snapshot the model already saw, and any later reasoning anchored on that snapshot is now wrong.

This is a discipline, not a guarantee. The current implementation injects cache values into the interpreter's locals by reference, so in-place mutation is technically possible. The harness does not deep-copy on injection — that would be expensive for large frames. The right fix is type-aware copy-on-injection (`df.copy()` for DataFrames, `arr.copy()` for ndarrays, a conservative fallback for unknown mutable types). For now, the model is expected to use `save`, and the harness leans on the discipline rather than enforcing it.

---

## Three forms of the same value

The same cached value lives in three places:

- the **raw payload** sits in the cache itself; nothing else holds it
- the **snapshot** sits in message history as part of the tool result; this is what the model reads
- the **identifier** sits in the interpreter's local scope when Python is invoked; this is what the model writes against

Each form is right for its surface. The raw payload would be ruinous in message history. The snapshot would be useless inside the interpreter. The identifier on its own would be opaque without a snapshot to remind the model what it points at.

The cache is the only place the raw payload exists. Everything else points at it.

---

## Handles proliferate

Immutability has a cost: derivations accumulate.

A typical session of incremental work leaves a trail behind it. Fetch sales data. Filter to a date range. Drop nulls. Group by region. Pivot for a comparison. Each step, written correctly, produces a new cached handle:

```
sales_orders                     [100000, 8]
sales_orders_recent              [12000,  8]
sales_orders_recent_clean        [11800,  8]
sales_orders_by_region           [42,     4]
sales_pivot_region_month         [42,    13]
```

All five are valid handles. All five are still in memory. `list_variables` becomes noisy. The cache fills with near-duplicates that the agent might or might not return to. There is no built-in eviction in the current implementation. That is the next problem to solve.

---

## Eviction is the open question

What is the right eviction policy?

Two candidates seem worth thinking through.

*LRU.* The simplest. Track when each handle was last touched and, under memory pressure, evict the least recently used. Familiar, easy to reason about. The risk is that an agent's access pattern is not always recency-shaped: it may load a baseline early, work on derivations for ten turns, then come back to the baseline. Pure LRU would have evicted it.

*Explicit retire.* A `retire(handle)` operation lets the model declare "I am done with this." Honest and transparent, but it asks the model to reason about its own working set, which is one more thing to get wrong.

Neither is obviously correct. LRU is easy to implement but may evict a baseline the agent still needs. Explicit retire is honest but adds another operation the model has to use deliberately. The honest answer is: this is open.

The next implementation step is more conservative than picking an eviction policy. It is to push pressure to disk before deciding what to drop.

---

## Disk-backed spillover

A long session does not need every cached value resident in memory. It needs every cached value addressable by handle.

Those are different requirements, and the gap is what disk-backed spillover fills.

The plan: the cache keeps a hot set of recently used handles in memory, and spills the rest to disk while preserving the handle/snapshot contract intact. An initial proposal is to keep the ten most recently used handles hot; ten is not special, but it is enough to prove the hot/cold behaviour before tuning policy. Older handles age out to disk. "Recently used" means any of `put`, `get`, interpreter injection, `list_variables` enumeration, or being passed as a subagent input handle.

Crucially, the model never sees disk paths or storage formats. It still sees handles and snapshots. A `get` on a cold handle hydrates the value from disk transparently and updates recency, which may push some other hot value out. The interface is unchanged; only the storage moves.

Serialisation is type-aware where it matters:

- DataFrames spill to Parquet
- NumPy arrays spill to `.npy` or `.npz`
- unknown Python objects fall back to pickle as a last resort, with the obvious caveats

Logs record handle metadata and storage location, but never the raw payload — the same rule the harness applies everywhere else. If the log became a second place where full datasets are dumped, the harness would have only moved the context problem somewhere slower.

A long session looks like this:

```
turn 4:  fetch sales_orders         -> hot
turn 6:  fetch telemetry_events     -> hot
turn 9:  derive sales_orders_clean  -> hot
turn 14: derive crm_join            -> hot
... six more derivations ...
turn 22: sales_orders ages to disk (Parquet)
turn 27: model calls list_variables -> sales_orders snapshot still surfaced
turn 28: model uses sales_orders in interpreter -> hydrated transparently
```

The model sees no change in interface. The harness sees a bounded memory footprint.

For a data agent, this is the right default before any eviction policy. Agents return to earlier work. The cost of a Parquet read is much smaller than the cost of having to recompute a connector call, and dramatically smaller than the cost of getting an answer wrong because a baseline frame disappeared.

---

## The subagent boundary

Subagents are a special case of cache transfer.

When the parent delegates work, it can pass `input_handles=[...]`. The cache copies the named values into the subagent's fresh cache. The values never travel through the prompt — they cross as cache state.

In the current implementation, that copy is by reference. The sub-cache holds the same Python object as the parent cache. For immutable types (strings, numbers) this is fine. For DataFrames, NumPy arrays, and other mutable containers, it is a back-channel: a subagent that runs `sales_orders.dropna(inplace=True)` quietly mutates the parent's cached frame. Neither the parent's message history nor its planner state shows that anything changed.

That violates the principle the rest of the design rests on. State is supposed to cross boundaries deliberately. A subagent's effect on the parent should appear in the parent's transcript, not in a frame the parent assumed was stable.

The fix is type-aware copy at the boundary:

- DataFrames copied with `df.copy()`
- NumPy arrays copied with `arr.copy()`
- unknown mutable Python objects fall back to a conservative deepcopy or are flagged as unsupported

The reverse direction has its own issue. When a subagent finishes with `output_policy="publish_created"`, any handle it created during its run is published to the parent cache. Parent and sub may both have meaningful state under the same handle name. The contract is straightforward: parent-side collisions never overwrite. The cache uses the same suffixing rule it uses everywhere else (`summary` becomes `summary_2`), and the tool result reports the resolved parent-side name, not the subagent's local one.

```
subagent input:
    parent has   sales_orders, weekly_summary
    sub gets     sales_orders (copied), weekly_summary (copied)

subagent publishes 'weekly_summary' (newly computed inside the sub)
    parent already has  weekly_summary
    parent stores       weekly_summary_2
    tool result text:   "summary -> weekly_summary_2"
```

These are details, but they are the details that decide whether subagent isolation is real or only nominal.

---

## The cache is the working memory

When you take bash away from a data agent, you do not just remove a tool. You remove the model-facing part of the environment the agent would otherwise have leaned on for state.

The session cache is what fills that gap. Handles take the place of filenames. Snapshots take the place of `ls` and `head`. `save` takes the place of writing a new file rather than editing in place. Disk-backed spillover takes the place of moving older work to slower storage. Eviction — once it exists — will take the place of `rm`.

None of these is a one-to-one replacement. Handles are not paths. Snapshots are not files. The cache has no directories, no permissions, no symlinks. But the role the cache plays in the harness is the role a filesystem would play in a shell-equipped agent: it is where the agent's working memory lives, and the rules around it decide whether the rest of the design holds.

Most of the engineering judgement in this harness ends up in the cache. That is not a side effect of the design. It is the design.

The fuller implementation is in [`dataact`](https://github.com/maxkskhor/dataact) — the cache lives in `dataact/cache.py` and the format dispatch lives in `dataact/format.py`. Disk-backed spillover and the subagent boundary copy are in the next release. A separate `learn-dataact` repo will later distil the teaching version after the SDK surface stabilises.
