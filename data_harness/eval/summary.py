"""Render committed JSON eval results into a human-readable ``SUMMARY.md``.

The per-run JSON (from ``EvalReport.to_dict``) is machine-readable but hard to
skim. This turns a directory of result JSONs into one Markdown file of
leaderboard tables — so anyone browsing the repo sees the numbers immediately.

    python -m data_harness.eval.summary        # regenerate evals/results/SUMMARY.md
"""

from __future__ import annotations

import json
from pathlib import Path


def leaderboard_markdown(report: dict) -> str:
    """A Markdown accuracy/turns/tokens/cost table from a ``to_dict`` report."""
    lines = [
        "| model | accuracy | avg turns | tokens | cost ($) |",
        "|---|---|---|---|---|",
    ]
    models = report.get("models", {})
    for model, entry in sorted(
        models.items(), key=lambda kv: -kv[1].get("accuracy", 0)
    ):
        cost = entry.get("cost_usd")
        cost_str = f"{cost:.4f}" if isinstance(cost, (int, float)) else "n/a"
        lines.append(
            f"| {model} | {entry.get('accuracy', 0):.0%} | "
            f"{entry.get('avg_turns', 0):.1f} | {entry.get('tokens', 0):,} | "
            f"{cost_str} |"
        )
    return "\n".join(lines)


def write_summary(results_dir: str | Path = "evals/results") -> Path:
    """Regenerate ``<results_dir>/SUMMARY.md`` from all result JSONs there."""
    directory = Path(results_dir)
    files = sorted(directory.glob("*.json"), reverse=True)  # newest first

    out = [
        "# Evaluation results",
        "",
        "Human-readable leaderboards (newest first). Regenerate with "
        "`python -m data_harness.eval.summary`.",
        "",
        "What the suites mean: **hard / large-data** validate the *design* "
        "(joins, multi-step, stateful, 100k-row handle work) and tend to "
        "saturate; **messy** and **WikiTableQuestions** are where models "
        "actually diverge.",
        "",
    ]
    for path in files:
        data = json.loads(path.read_text())
        report = data.get("report", {})
        suite = data.get("suite") or data.get("benchmark") or path.stem
        when = (data.get("generated_at") or "")[:10]
        out.append(f"## {suite} · {when}")
        out.append(
            f"_{report.get('n_runs', '?')} runs · overall accuracy "
            f"{report.get('accuracy', 0):.0%}_"
        )
        out.append("")
        out.append(leaderboard_markdown(report))
        out.append("")
        out.append(f"<sub>source: `{path.name}`</sub>")
        out.append("")

    summary = directory / "SUMMARY.md"
    summary.write_text("\n".join(out))
    return summary


def main() -> None:
    path = write_summary()
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
