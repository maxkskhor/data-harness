"""Run an evaluation suite across recent models; print a cost leaderboard and
write a tracked JSON report.

Suites:
- ``hard``    — multi-table joins, deep multi-step, stateful multi-turn (default;
                stretches the harness: long turns + SessionCache).
- ``bespoke`` — simpler single-shot smoke set.

Uses OpenRouter (one key, many providers). Needs OPENROUTER_API_KEY and the
[eval] extra. Spends a few cents on cheap models.

    uv run python examples/eval_demo.py               # hard suite, default models
    uv run python examples/eval_demo.py --suite bespoke
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from dotenv import load_dotenv

from data_harness.eval import (
    bespoke_suite,
    evaluate_matrix,
    fetch_openrouter_prices,
    hard_suite,
    large_data_suite,
    messy_suite,
)

# Recent, cheap, capable models across diverse providers. (Dropped gpt-4o-mini —
# too old — and claude-haiku-4.5 — far pricier than open models of similar
# capability here.) Adjust freely.
DEFAULT_MODELS = [
    "deepseek/deepseek-v4-flash",  # DeepSeek
    "qwen/qwen3.5-flash-02-23",  # Alibaba Qwen
    "openai/gpt-5-nano",  # OpenAI
    "google/gemini-2.5-flash-lite",  # Google
    "z-ai/glm-4.7-flash",  # Z.ai
]

SUITES = {
    "hard": hard_suite,
    "bespoke": bespoke_suite,
    "large": large_data_suite,
    "messy": messy_suite,
}


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=SUITES, default="hard")
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    parser.add_argument("--run-dir", default="./runs/eval")
    parser.add_argument("--out", default=None, help="JSON report path")
    parser.add_argument("--no-cost", action="store_true")
    args = parser.parse_args()

    cases = SUITES[args.suite]()
    print(f"[{args.suite}] {len(cases)} cases × {len(args.models)} models\n")

    def progress(r):
        print(f"  {'✓' if r.passed else '✗'} [{r.model}] {r.case_id} ({r.turns}t)")

    report = evaluate_matrix(cases, args.models, run_dir=args.run_dir, on_case=progress)
    prices = None if args.no_cost else fetch_openrouter_prices(args.models)
    print("\n" + report.to_markdown(prices))

    stamp = dt.datetime.now().strftime("%Y%m%dt%H%M%S")
    out = Path(args.out or f"evals/results/{args.suite}_{stamp}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "suite": args.suite,
                "models": args.models,
                "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "report": report.to_dict(prices),
            },
            indent=2,
            default=str,
        )
    )
    print(f"\nWrote tracked report → {out}")


if __name__ == "__main__":
    main()
