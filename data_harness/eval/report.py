"""Per-case results and aggregated evaluation reports."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field


@dataclass
class CaseResult:
    """The graded outcome of running one case under one model."""

    case_id: str
    category: str
    model: str
    passed: bool
    detail: str
    turns: int
    input_tokens: int
    output_tokens: int
    latency_ms: float
    status: str
    error: str | None = None


@dataclass
class EvalReport:
    """Aggregated results across cases (and optionally models)."""

    results: list[CaseResult] = field(default_factory=list)

    def accuracy(self) -> float:
        if not self.results:
            return 0.0
        return sum(r.passed for r in self.results) / len(self.results)

    @property
    def models(self) -> list[str]:
        seen: dict[str, None] = {}
        for r in self.results:
            seen.setdefault(r.model, None)
        return list(seen)

    @property
    def categories(self) -> list[str]:
        seen: dict[str, None] = {}
        for r in self.results:
            seen.setdefault(r.category, None)
        return list(seen)

    def _subset(self, *, model: str | None = None, category: str | None = None):
        return [
            r
            for r in self.results
            if (model is None or r.model == model)
            and (category is None or r.category == category)
        ]

    @staticmethod
    def _rate(rows: list[CaseResult]) -> float:
        return sum(r.passed for r in rows) / len(rows) if rows else 0.0

    @staticmethod
    def _cost(
        rows: list[CaseResult], price: tuple[float, float] | None
    ) -> float | None:
        """USD cost for ``rows`` given ``(prompt_$/Mtok, completion_$/Mtok)``."""
        if price is None:
            return None
        prompt_per_m, completion_per_m = price
        total = sum(
            r.input_tokens * prompt_per_m + r.output_tokens * completion_per_m
            for r in rows
        )
        return total / 1_000_000

    def total_cost(self, prices: dict[str, tuple[float, float]]) -> float:
        """Total USD cost across all models, given per-model price tuples."""
        return sum(
            self._cost(self._subset(model=m), prices.get(m)) or 0.0 for m in self.models
        )

    def leaderboard(self, prices: dict[str, tuple[float, float]] | None = None) -> str:
        """Markdown table of accuracy / tokens / turns (and cost, if priced)."""
        cols = ["model", "accuracy", "passed", "avg turns", "total tokens"]
        if prices is not None:
            cols.append("cost ($)")
        lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
        ranked = sorted(self.models, key=lambda m: -self._rate(self._subset(model=m)))
        for model in ranked:
            rows = self._subset(model=model)
            passed = sum(r.passed for r in rows)
            avg_turns = sum(r.turns for r in rows) / len(rows) if rows else 0
            tokens = sum(r.input_tokens + r.output_tokens for r in rows)
            cells = [
                model,
                f"{self._rate(rows):.0%}",
                f"{passed}/{len(rows)}",
                f"{avg_turns:.1f}",
                f"{tokens:,}",
            ]
            if prices is not None:
                cost = self._cost(rows, prices.get(model))
                cells.append(f"{cost:.4f}" if cost is not None else "n/a")
            lines.append("| " + " | ".join(cells) + " |")
        return "\n".join(lines)

    def by_category(self) -> str:
        """Markdown table of accuracy per category (× model)."""
        models = sorted(self.models)
        header = "| category | " + " | ".join(models) + " |"
        sep = "|---" * (len(models) + 1) + "|"
        lines = [header, sep]
        for cat in sorted(self.categories):
            cells = [
                f"{self._rate(self._subset(model=m, category=cat)):.0%}" for m in models
            ]
            lines.append(f"| {cat} | " + " | ".join(cells) + " |")
        return "\n".join(lines)

    def failures(self) -> list[CaseResult]:
        return [r for r in self.results if not r.passed]

    def to_markdown(self, prices: dict[str, tuple[float, float]] | None = None) -> str:
        heading = (
            f"## Evaluation report — {len(self.results)} runs, "
            f"overall accuracy {self.accuracy():.0%}"
        )
        if prices is not None:
            heading += f", total cost ${self.total_cost(prices):.4f}"
        parts = [
            heading,
            "",
            "### Leaderboard",
            self.leaderboard(prices),
            "",
            "### By category",
            self.by_category(),
        ]
        fails = self.failures()
        if fails:
            parts += ["", f"### Failures ({len(fails)})"]
            parts += [f"- `{r.model}` / `{r.case_id}`: {r.detail}" for r in fails[:25]]
        return "\n".join(parts)

    def to_dict(self, prices: dict[str, tuple[float, float]] | None = None) -> dict:
        """Machine-readable summary for tracking results over time."""
        models: dict[str, dict] = {}
        for model in self.models:
            rows = self._subset(model=model)
            entry = {
                "accuracy": self._rate(rows),
                "passed": sum(r.passed for r in rows),
                "total": len(rows),
                "avg_turns": sum(r.turns for r in rows) / len(rows) if rows else 0,
                "tokens": sum(r.input_tokens + r.output_tokens for r in rows),
            }
            if prices is not None:
                entry["cost_usd"] = self._cost(rows, prices.get(model))
            models[model] = entry
        return {
            "n_runs": len(self.results),
            "accuracy": self.accuracy(),
            "models": models,
            "by_category": {
                cat: {
                    m: self._rate(self._subset(model=m, category=cat))
                    for m in self.models
                }
                for cat in self.categories
            },
            "results": [asdict(r) for r in self.results],
        }

    def to_json(
        self, prices: dict[str, tuple[float, float]] | None = None, *, indent: int = 2
    ) -> str:
        """JSON form of `to_dict`, suitable for writing a tracked report file."""
        return json.dumps(self.to_dict(prices), indent=indent, default=str)

    def _repr_markdown_(self) -> str:
        return self.to_markdown()

    def __str__(self) -> str:
        return self.to_markdown()
