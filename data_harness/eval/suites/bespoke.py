"""A small, hand-written data-analysis suite with robust programmatic graders.

Covers aggregation, filtering, group-by, lookup, multi-step reasoning, charting,
and an adversarial unanswerable case. Graders favour numeric/contains/chart/
refusal checks so live pass-rates reflect reasoning, not output formatting.
"""

from __future__ import annotations

from data_harness.eval.case import EvalCase
from data_harness.eval.graders import (
    all_of,
    chart_produced,
    contains,
    numeric,
    refuses,
)


def _sales():
    import pandas as pd

    return pd.DataFrame(
        {
            "month": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
            "revenue": [120, 150, 90, 200, 175, 230],
            "region": ["NA", "NA", "EU", "EU", "APAC", "APAC"],
        }
    )


def _employees():
    import pandas as pd

    return pd.DataFrame(
        {
            "name": ["Ann", "Bob", "Cara", "Dan", "Eve"],
            "dept": ["Eng", "Eng", "Sales", "Sales", "Eng"],
            "salary": [120, 110, 90, 95, 130],
            "years": [5, 3, 8, 2, 6],
        }
    )


def _timeseries():
    import pandas as pd

    return pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=6, freq="MS"),
            "value": [1.0, 1.2, 0.9, 1.5, 1.3, 1.7],
        }
    )


def bespoke_suite() -> list[EvalCase]:
    """Return the bespoke evaluation cases."""
    sales, employees, ts = _sales(), _employees(), _timeseries()
    return [
        EvalCase(
            "total_revenue",
            "What is the total revenue across all months?",
            sales,
            numeric(965),
            category="aggregation",
        ),
        EvalCase(
            "mean_salary",
            "What is the average salary?",
            employees,
            numeric(109, tol=0.5),
            category="aggregation",
        ),
        EvalCase(
            "mean_tenure",
            "What is the average number of years of tenure?",
            employees,
            numeric(4.8, tol=0.05),
            category="aggregation",
        ),
        EvalCase(
            "count_eng",
            "How many employees are in the Engineering department?",
            employees,
            numeric(3),
            category="filter",
        ),
        EvalCase(
            "top_region",
            "Which region has the highest total revenue?",
            sales,
            contains("APAC"),
            category="groupby",
        ),
        EvalCase(
            "eu_total",
            "What is the total revenue from the EU region?",
            sales,
            numeric(290),
            category="groupby",
        ),
        EvalCase(
            "top2_paid",
            "Who are the two highest-paid employees? Give their names.",
            employees,
            all_of(contains("Eve"), contains("Ann")),
            category="sort",
        ),
        EvalCase(
            "highest_month",
            "Which month had the highest revenue?",
            sales,
            contains(["Jun", "June"]),
            category="lookup",
        ),
        EvalCase(
            "lowest_month",
            "Which month had the lowest revenue?",
            sales,
            contains(["Mar", "March"]),
            category="lookup",
        ),
        EvalCase(
            "eu_share",
            "What percentage of total revenue came from the EU region?",
            sales,
            numeric(30.05, tol=0.8),
            category="multi_step",
        ),
        EvalCase(
            "eu_minus_na",
            "How much higher is EU total revenue than NA total revenue?",
            sales,
            numeric(20),
            category="multi_step",
        ),
        EvalCase(
            "chart_revenue",
            "Plot total revenue by month as a bar chart.",
            sales,
            chart_produced(),
            category="chart",
        ),
        EvalCase(
            "chart_timeseries",
            "Plot the value over time as a line chart.",
            ts,
            chart_produced(),
            category="chart",
        ),
        EvalCase(
            "unanswerable",
            "What is the customer churn rate for this data?",
            sales,
            refuses(),
            category="adversarial",
        ),
    ]
