# dataact — Completed Runtime Work (v3 roadmap)

These items were originally framed as teaching-focused improvements. They are now part of the framework's runtime foundation: state, subagent transfer, and a concrete demo. The distilled teaching version belongs in the future `learn-dataact` repository after the SDK stabilises.

---

## 1. Disk-backed session cache

**Current:** `SessionCache` keeps all handles in memory for the lifetime of the process.

**Goal:** persist older cached values to disk so long-running sessions do not keep every raw object resident in memory indefinitely. Values should remain addressable by handle and load back from disk on demand when a tool or interpreter needs them.

Design notes:
- Keep the handle/snapshot contract unchanged: the model still sees compact snapshots, not paths or raw payloads.
- Add a storage policy to `SessionCache` for deciding when a value remains hot in memory vs. is spilled to disk.
- Design the hot/cold policy explicitly. Initial candidate: keep the 10 most recently used handles hot in memory, mark older handles cold, and spill their raw tool results to disk.
- Define what counts as "recently used": `put`, `get`, interpreter injection, `list_variables`, subagent `input_handles`, or only raw-value access.
- `get(handle)` should transparently hydrate a disk-backed value when needed.
- Hydrating a cold value should update its recency and may spill another hot value if the hot-set limit is reached.
- Prefer structured serialisation by value type where possible (Parquet for DataFrames, `.npy`/`.npz` for arrays, pickle/cloudpickle only as a fallback).
- Logs should record handle metadata and storage location/type, but not raw payload contents.
- Subagent `input_handles` and `publish_created` should continue to copy by explicit handle, with disk-backed values handled transparently.
- Add tests for spill, hydrate, recency updates, process cleanup, and handle deletion/lifetime semantics.

---

## 2. Subagent cache-boundary edge cases

**Current:** subagent input handles are seeded with `sub_cache.put(handle, parent_cache.get(handle))`. That is a reference copy, not a value copy. For mutable objects such as DataFrames or ndarrays, an in-place mutation inside the subagent can mutate the parent's cached object through a back-channel that is absent from both the parent message history and the planner state.

**Goal:** make subagent state transfer preserve the explicit-state boundary: parent-owned cached values must not be mutated by a subagent unless the subagent publishes a new or explicitly updated handle through the declared output path.

Design notes:
- Add a cache-boundary copy policy for `input_handles`.
- Prefer type-aware copying over unconditional `copy.deepcopy` where practical: pandas DataFrames can use `df.copy(...)`, numpy arrays can use `arr.copy()`, and unknown mutable Python objects may need a conservative fallback or a documented unsupported path.
- Decide whether DataFrame copies should be shallow or deep. Shallow copies reduce memory cost but may still share underlying blocks in some mutation patterns; the invariant should be tested against representative in-place operations.
- Keep raw data out of prompts: copying must happen inside cache/runtime plumbing, not through message serialization.
- Add tests proving that subagent in-place mutations to input handles do not alter parent cache values.

Second edge case: published subagent handles can collide with existing parent handles. The current `SessionCache.put` suffixes collisions (`name`, `name_2`, ...), and `publish_created` reports `sub_name -> parent_name`. Keep that behavior, but make it an explicit contract:
- Parent-side publish collisions must never overwrite existing parent handles.
- Returned tool text must use the resolved parent handle names, not only the subagent's local names.
- Add tests for collisions between subagent-created handles and parent session variables/handles.

---

## 3. Real demo dataset

**Current:** synthetic OHLCV data generated in `examples/advanced_wiring.py`.

**Goal:** ship `examples/` with a real, publicly licensed dataset.

Possible datasets:
- FRED macro data.
- NYC taxi sample.
- Another small, stable, permissively licensed tabular dataset.

Design notes:
- Keep the demo runnable without private infrastructure.
- Prefer a checked-in small sample or deterministic download script over a live external dependency.
- The dataset should exercise the handle/snapshot pattern, connector loading, interpreter analysis, planner reminders, and subagent path without making setup heavier.
