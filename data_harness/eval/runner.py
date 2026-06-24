"""Run evaluation cases and collect graded results."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from time import perf_counter
from typing import TYPE_CHECKING, Any

from data_harness.eval.report import CaseResult, EvalReport
from data_harness.quickstart import ask

if TYPE_CHECKING:
    from data_harness.eval.case import EvalCase
    from data_harness.providers.base import ProviderAdapter


def evaluate(
    cases: Iterable[EvalCase],
    *,
    model: str | None = None,
    adapter: ProviderAdapter | None = None,
    model_label: str | None = None,
    run_dir: str | None = None,
    max_turns: int = 12,
    on_case: Callable[[CaseResult], None] | None = None,
    **ask_kwargs: Any,
) -> EvalReport:
    """Run every case once and grade it.

    Args:
        cases: The cases to run.
        model: Model id passed to `ask` (routes to the matching provider).
        adapter: Explicit adapter, overriding ``model``.
        model_label: Label used in the report (defaults to ``model`` or the
            adapter class name).
        run_dir: Directory for JSONL logs / chart artefacts.
        max_turns: Per-case turn cap.
        on_case: Optional callback invoked with each `CaseResult` as it lands.
        **ask_kwargs: Forwarded to `ask` (e.g. ``sql=False``).

    Returns:
        An `EvalReport`.
    """
    label = model_label or model or (type(adapter).__name__ if adapter else "default")
    results: list[CaseResult] = []

    for case in cases:
        start = perf_counter()
        try:
            result = ask(
                case.data,
                case.question,
                model=model,
                adapter=adapter,
                semantics=case.semantics,
                max_turns=max_turns,
                run_dir=run_dir,
                **ask_kwargs,
            )
        except Exception as exc:  # noqa: BLE001 - record, don't abort the suite
            results.append(
                CaseResult(
                    case_id=case.id,
                    category=case.category,
                    model=label,
                    passed=False,
                    detail=f"run error: {exc!r}",
                    turns=0,
                    input_tokens=0,
                    output_tokens=0,
                    latency_ms=(perf_counter() - start) * 1000,
                    status="error",
                    error=repr(exc),
                )
            )
            if on_case is not None:
                on_case(results[-1])
            continue

        latency_ms = (perf_counter() - start) * 1000
        grade = case.grader(result, case)
        case_result = CaseResult(
            case_id=case.id,
            category=case.category,
            model=label,
            passed=grade.passed,
            detail=grade.detail,
            turns=result.turns,
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            latency_ms=latency_ms,
            status=result.status,
            error=result.error,
        )
        results.append(case_result)
        if on_case is not None:
            on_case(case_result)

    return EvalReport(results)


def evaluate_matrix(
    cases: Iterable[EvalCase],
    models: list,
    **kwargs: Any,
) -> EvalReport:
    """Run the same cases across several models and merge into one report.

    Args:
        cases: The cases to run (materialised once and reused per model).
        models: Either model-id strings (e.g. ``"openai/gpt-4o-mini"``) or
            ``(label, adapter)`` tuples (handy for tests / custom clients).
        **kwargs: Forwarded to `evaluate`.

    Returns:
        A combined `EvalReport` across all models.
    """
    cases = list(cases)
    merged: list[CaseResult] = []
    for entry in models:
        if isinstance(entry, tuple):
            label, adapter = entry
            report = evaluate(cases, adapter=adapter, model_label=label, **kwargs)
        else:
            report = evaluate(cases, model=entry, **kwargs)
        merged.extend(report.results)
    return EvalReport(merged)
