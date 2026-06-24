"""Evaluation harness for data-harness agents.

Define `EvalCase`s with programmatic graders, run them across one or many models
(`evaluate` / `evaluate_matrix`), and read an `EvalReport` (accuracy, leaderboard,
per-category breakdown, failures). Grading leans on the structured
``RunResult.value`` produced by ``answer()``.
"""

from data_harness.eval.case import EvalCase, Grader
from data_harness.eval.graders import (
    Grade,
    all_of,
    any_of,
    chart_produced,
    contains,
    dataframe_equals,
    exact,
    extract_numbers,
    numeric,
    refuses,
)
from data_harness.eval.report import CaseResult, EvalReport
from data_harness.eval.runner import evaluate, evaluate_matrix
from data_harness.eval.suites import (
    bespoke_suite,
    load_wikitablequestions,
    wtq_row_to_case,
)

__all__ = [
    "CaseResult",
    "EvalCase",
    "EvalReport",
    "Grade",
    "Grader",
    "all_of",
    "any_of",
    "bespoke_suite",
    "chart_produced",
    "contains",
    "dataframe_equals",
    "evaluate",
    "evaluate_matrix",
    "exact",
    "extract_numbers",
    "load_wikitablequestions",
    "numeric",
    "refuses",
    "wtq_row_to_case",
]
