"""Per-case results and aggregated evaluation reports."""

from __future__ import annotations

from dataclasses import dataclass, field


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

    def leaderboard(self) -> str:
        """Markdown table of accuracy / tokens / turns per model."""
        header = (
            "| model | accuracy | passed | avg turns | total tokens |\n"
            "|---|---|---|---|---|"
        )
        lines = [header]
        ranked = sorted(self.models, key=lambda m: -self._rate(self._subset(model=m)))
        for model in ranked:
            rows = self._subset(model=model)
            passed = sum(r.passed for r in rows)
            avg_turns = sum(r.turns for r in rows) / len(rows) if rows else 0
            tokens = sum(r.input_tokens + r.output_tokens for r in rows)
            lines.append(
                f"| {model} | {self._rate(rows):.0%} | {passed}/{len(rows)} | "
                f"{avg_turns:.1f} | {tokens:,} |"
            )
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

    def to_markdown(self) -> str:
        parts = [
            f"## Evaluation report — {len(self.results)} runs, "
            f"overall accuracy {self.accuracy():.0%}",
            "",
            "### Leaderboard",
            self.leaderboard(),
            "",
            "### By category",
            self.by_category(),
        ]
        fails = self.failures()
        if fails:
            parts += ["", f"### Failures ({len(fails)})"]
            parts += [f"- `{r.model}` / `{r.case_id}`: {r.detail}" for r in fails[:25]]
        return "\n".join(parts)

    def _repr_markdown_(self) -> str:
        return self.to_markdown()

    def __str__(self) -> str:
        return self.to_markdown()
