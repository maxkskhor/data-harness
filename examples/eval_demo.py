"""Run the bespoke evaluation suite across several models and print a leaderboard.

Uses OpenRouter (one key, many providers). Needs OPENROUTER_API_KEY and spends a
few cents on cheap models.

    uv run python examples/eval_demo.py
    uv run python examples/eval_demo.py --models openai/gpt-4o-mini deepseek/deepseek-chat
"""

from __future__ import annotations

import argparse

from dotenv import load_dotenv

from data_harness.eval import bespoke_suite, evaluate_matrix

DEFAULT_MODELS = [
    "openai/gpt-4o-mini",
    "anthropic/claude-haiku-4.5",
    "deepseek/deepseek-chat",
]


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    parser.add_argument("--run-dir", default="./runs/eval")
    args = parser.parse_args()

    cases = bespoke_suite()
    print(f"Running {len(cases)} cases × {len(args.models)} models...\n")

    def progress(r):
        mark = "✓" if r.passed else "✗"
        print(f"  {mark} [{r.model}] {r.case_id} ({r.turns} turns) — {r.detail[:60]}")

    report = evaluate_matrix(
        cases, args.models, run_dir=args.run_dir, on_case=progress
    )

    print("\n" + report.to_markdown())


if __name__ == "__main__":
    main()
