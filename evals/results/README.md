# Evaluation results

**Start here: [`SUMMARY.md`](SUMMARY.md)** — a readable leaderboard table per
suite (accuracy, turns, tokens, cost), newest first.

Each run also writes a pair of files:

- `<suite>_<timestamp>.md` — the full leaderboard for that run (human-readable).
- `<suite>_<timestamp>.json` — the same data machine-readable
  (`EvalReport.to_dict`: accuracy, per-model & per-category, cost, every case),
  for diffing/tracking over time.

These are produced by the example runners and committed so quality is tracked in
git (per-run JSONL logs and chart artefacts stay in the gitignored `runs/`):

```bash
uv run python examples/eval_demo.py --suite messy   # bespoke / hard / large / messy
uv run python examples/eval_wtq.py --limit 50        # public WikiTableQuestions
python evals/summarize.py                            # rebuild SUMMARY.md
```

How to read it: the **hard** and **large-data** suites validate the *design*
(joins, multi-step, stateful multi-turn, 100k-row handle work) and tend to
saturate near 100% across capable models. **messy** (real-world cleaning) and
**WikiTableQuestions** are where models actually diverge.
