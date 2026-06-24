# Evaluation

`data_harness.eval` is a small harness for measuring how well an agent answers
real data questions — across models, with **programmatic grading**. It leans on
the structured `RunResult.value` produced by `answer()`, so most cases grade
without an LLM judge.

## A first run

```python
from data_harness.eval import bespoke_suite, evaluate

report = evaluate(bespoke_suite(), model="openai/gpt-4o-mini")
print(report.to_markdown())
print("accuracy:", report.accuracy())
```

`evaluate` runs each case through `ask`, grades the result, and records
pass/fail, turns, tokens, latency, and status.

## Cases and graders

A case pairs a question + dataset with a grader:

```python
from data_harness.eval import EvalCase, numeric, contains, chart_produced
import pandas as pd

sales = pd.DataFrame({"month": ["Jan", "Feb"], "revenue": [120, 150]})

cases = [
    EvalCase("total", "What is total revenue?", sales, numeric(270)),
    EvalCase("top", "Which month was highest?", sales, contains("Feb")),
    EvalCase("plot", "Plot revenue by month.", sales, chart_produced()),
]
```

Built-in graders (each checks `result.value` first, then the prose):

| Grader | Passes when |
|---|---|
| `numeric(expected, tol=…)` | the computed number matches within tolerance |
| `contains(expected)` | any expected string appears in value/prose |
| `exact(expected)` | `result.value` equals `expected` (normalised) |
| `dataframe_equals(df)` | `result.value` is an equal DataFrame |
| `chart_produced()` | the run rendered ≥1 chart |
| `refuses()` | the answer signals it can't/shouldn't answer (adversarial cases) |
| `all_of(...)` / `any_of(...)` | combine graders |

## Multi-model leaderboard

OpenRouter makes the model matrix one key away:

```python
from data_harness.eval import bespoke_suite, evaluate_matrix

report = evaluate_matrix(
    bespoke_suite(),
    ["openai/gpt-4o-mini", "anthropic/claude-haiku-4.5", "deepseek/deepseek-chat"],
)
print(report.leaderboard())     # accuracy / tokens / turns per model
print(report.by_category())     # accuracy per category × model
```

`models` may also be `(label, adapter)` tuples for custom clients or offline
tests with `FakeAdapter`.

### Cost per model

Pass a `{model: (prompt_$/Mtok, completion_$/Mtok)}` price map to add a USD cost
column. `fetch_openrouter_prices` pulls live prices for you:

```python
from data_harness.eval import fetch_openrouter_prices

models = ["deepseek/deepseek-v4-flash", "qwen/qwen3.5-flash-02-23"]
report = evaluate_matrix(bespoke_suite(), models)
prices = fetch_openrouter_prices(models)
print(report.to_markdown(prices))   # leaderboard now has a "cost ($)" column
```

## Public benchmark

WikiTableQuestions (table QA) loads via the `[eval]` extra:

```python
from data_harness.eval import load_wikitablequestions, evaluate

cases = load_wikitablequestions(split="validation", limit=50)
report = evaluate(cases, model="openai/gpt-4o-mini")
```

The row→case conversion (`wtq_row_to_case`) is exposed separately so you can plug
in other public benchmarks (DABStep, InfiAgent-DABench, Spider/BIRD) with the
same grading and reporting.

## Why this fits data-harness

- `answer()` → `.value` gives a **checkable** result, so grading is programmatic.
- **OpenRouter** turns the model matrix into a one-key leaderboard.
- **JSONL run logs** make every graded case reconstructable.
- The same harness quantifies reliability gaps (e.g. how often a model actually
  calls `answer()`), turning "it felt better" into a number.
