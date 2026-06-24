"""Run the bespoke evaluation suite across several models and print a leaderboard.

Uses OpenRouter (one key, many providers). Needs OPENROUTER_API_KEY and spends a
few cents on cheap models. Prices are fetched from OpenRouter so the leaderboard
includes a per-model USD cost column.

    uv run python examples/eval_demo.py
    uv run python examples/eval_demo.py --models deepseek/deepseek-v4-flash qwen/qwen3.5-flash-02-23
"""

from __future__ import annotations

import argparse

from dotenv import load_dotenv

from data_harness.eval import bespoke_suite, evaluate_matrix, fetch_openrouter_prices

DEFAULT_MODELS = [
    "deepseek/deepseek-v4-flash",
    "qwen/qwen3.5-flash-02-23",
    "openai/gpt-4o-mini",
    "anthropic/claude-haiku-4.5",
]


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    parser.add_argument("--run-dir", default="./runs/eval")
    parser.add_argument("--no-cost", action="store_true", help="skip cost column")
    args = parser.parse_args()

    cases = bespoke_suite()
    print(f"Running {len(cases)} cases × {len(args.models)} models...\n")

    def progress(r):
        mark = "✓" if r.passed else "✗"
        print(f"  {mark} [{r.model}] {r.case_id} ({r.turns} turns) — {r.detail[:60]}")

    report = evaluate_matrix(cases, args.models, run_dir=args.run_dir, on_case=progress)

    prices = None if args.no_cost else fetch_openrouter_prices(args.models)
    print("\n" + report.to_markdown(prices))


if __name__ == "__main__":
    main()
