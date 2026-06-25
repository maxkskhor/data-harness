# Evaluation results

Committed JSON reports from eval runs, so the metric is **tracked over time** and
diffable in git (the per-run JSONL logs and chart artefacts stay in the
gitignored `runs/`).

Each file is written by an example runner (`examples/eval_demo.py`,
`examples/eval_wtq.py`) and has the shape:

```json
{
  "suite": "hard",
  "models": ["deepseek/deepseek-v4-flash", "..."],
  "generated_at": "2026-06-25T...Z",
  "report": { "n_runs": ..., "accuracy": ..., "models": {...}, "by_category": {...}, "results": [...] }
}
```

`report` is `EvalReport.to_dict(prices)`. Commit a file here to record a run;
compare across commits to track quality, cost, and turns as models/prompts change.
File naming: `<suite>_<YYYYMMDDtHHMMSS>.json`.
