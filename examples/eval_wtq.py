"""Tracked-metric run: WikiTableQuestions across models, with a JSON report.

A harder public benchmark than the bespoke suite (real Wikipedia tables), so it
differentiates strong models that saturate the bespoke set. Writes a timestamped
JSON report you can keep and diff over time, and prints a cost leaderboard.

    uv run python examples/eval_wtq.py                       # default lineup, 25 cases
    uv run python examples/eval_wtq.py --limit 100 --models deepseek/deepseek-v4-flash

Needs OPENROUTER_API_KEY and the [eval] extra (datasets). Spends a few cents.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from dotenv import load_dotenv

from data_harness.eval import (
    evaluate_matrix,
    fetch_openrouter_prices,
    load_wikitablequestions,
    write_summary,
)

DEFAULT_MODELS = [
    "deepseek/deepseek-v4-flash",  # DeepSeek
    "qwen/qwen3.5-flash-02-23",  # Alibaba Qwen
    "openai/gpt-5-nano",  # OpenAI
    "google/gemini-2.5-flash-lite",  # Google
    "z-ai/glm-4.7-flash",  # Z.ai
]


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--split", default="test")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--run-dir", default="./runs/eval_wtq")
    parser.add_argument("--out", default=None, help="JSON report path")
    args = parser.parse_args()

    cases = load_wikitablequestions(split=args.split, limit=args.limit, seed=args.seed)
    print(f"WikiTableQuestions: {len(cases)} cases × {len(args.models)} models\n")

    def progress(r):
        print(f"  {'✓' if r.passed else '✗'} [{r.model}] {r.case_id} ({r.turns}t)")

    report = evaluate_matrix(cases, args.models, run_dir=args.run_dir, on_case=progress)
    prices = fetch_openrouter_prices(args.models)
    print("\n" + report.to_markdown(prices))

    out = args.out or (
        Path("evals/results")
        / f"wtq_{dt.datetime.now().strftime('%Y%m%dt%H%M%S')}.json"
    )
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "benchmark": "wikitablequestions",
        "split": args.split,
        "limit": args.limit,
        "seed": args.seed,
        "models": args.models,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "report": report.to_dict(prices),
    }
    Path(out).write_text(json.dumps(payload, indent=2, default=str))
    Path(out).with_suffix(".md").write_text(report.to_markdown(prices))
    write_summary(Path(out).parent)
    print(f"\nWrote tracked report → {out} (+ .md, refreshed SUMMARY.md)")


if __name__ == "__main__":
    main()
