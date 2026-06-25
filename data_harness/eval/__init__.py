"""Evaluation harness for data-harness agents.

Define `EvalCase`s with programmatic graders, run them across one or many models
(`evaluate` / `evaluate_matrix`), and read an `EvalReport` (accuracy, leaderboard,
per-category breakdown, failures). Grading leans on the structured
``RunResult.value`` produced by ``answer()``.
"""

from data_harness.eval.case import ConversationCase, EvalCase, Grader, Turn
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
from data_harness.eval.pricing import fetch_openrouter_prices
from data_harness.eval.report import CaseResult, EvalReport
from data_harness.eval.runner import evaluate, evaluate_matrix
from data_harness.eval.suites import (
    bespoke_suite,
    hard_suite,
    large_data_suite,
    load_wikitablequestions,
    messy_suite,
    wtq_row_to_case,
)
from data_harness.eval.summary import leaderboard_markdown, write_summary

__all__ = [
    "CaseResult",
    "ConversationCase",
    "EvalCase",
    "EvalReport",
    "Grade",
    "Grader",
    "Turn",
    "all_of",
    "any_of",
    "bespoke_suite",
    "hard_suite",
    "large_data_suite",
    "messy_suite",
    "chart_produced",
    "contains",
    "dataframe_equals",
    "evaluate",
    "evaluate_matrix",
    "exact",
    "extract_numbers",
    "fetch_openrouter_prices",
    "leaderboard_markdown",
    "load_wikitablequestions",
    "numeric",
    "refuses",
    "wtq_row_to_case",
    "write_summary",
]
