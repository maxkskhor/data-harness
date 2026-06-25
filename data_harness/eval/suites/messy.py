"""A messy-data suite — the kind that actually differentiates models.

The clean/structured suites saturate (capable models + the harness handle them).
Real-world friction is where models diverge: amounts stored as strings with
currency symbols and thousands separators, dates in several formats, categorical
labels written inconsistently, and missing values. Each task requires *cleaning*
before computing.

Ground truth is computed in-suite by a reference cleaner, so the canonical answer
is unambiguous and the grader stays exact; the model has to reproduce that
cleaning to pass.
"""

from __future__ import annotations

from data_harness.eval.case import EvalCase
from data_harness.eval.graders import numeric


def _messy_transactions():
    import pandas as pd

    return pd.DataFrame(
        {
            "id": list(range(1, 11)),
            "amount": [
                "$1,200.50",
                "1,000",
                "750",
                "N/A",
                "300",
                "$450.00",
                "",
                "2,500",
                "600",
                "1,250",
            ],
            "date": [
                "2024-01-05",
                "01/15/2024",
                "March 3, 2024",
                "2024-02-10",
                "2024/02/20",
                "2024-03-01",
                "2024-03-15",
                "Feb 28, 2024",
                "2024-04-01",
                "2024/04/10",
            ],
            "country": [
                "US",
                "USA",
                "United States",
                "us ",
                "UK",
                "Canada",
                "UK",
                "US",
                "Canada",
                "united states ",
            ],
        }
    )


def _clean_amount(value) -> float | None:
    text = str(value).strip().replace("$", "").replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def messy_suite() -> list[EvalCase]:
    """Cases that require parsing/normalising messy real-world data."""
    import pandas as pd

    df = _messy_transactions()
    amounts = df["amount"].map(_clean_amount)
    country = (
        df["country"]
        .str.strip()
        .str.lower()
        .replace({"usa": "us", "united states": "us"})
    )
    dates = pd.to_datetime(df["date"], format="mixed")

    total = round(float(amounts.dropna().sum()), 2)
    us_mask = country == "us"
    us_count = int(us_mask.sum())
    us_total = round(float(amounts[us_mask].dropna().sum()), 2)
    q1_count = int(((dates.dt.year == 2024) & (dates.dt.month <= 3)).sum())

    return [
        EvalCase(
            "messy_total",
            "What is the total transaction amount? Amounts are strings that may "
            "include $ and thousands separators; ignore missing/'N/A' values.",
            df,
            numeric(total, tol=0.5),
            category="messy_parse",
        ),
        EvalCase(
            "messy_us_count",
            "How many transactions are from the United States? The country column "
            "uses inconsistent labels (US, USA, United States, ...).",
            df,
            numeric(us_count),
            category="messy_normalise",
        ),
        EvalCase(
            "messy_us_total",
            "What is the total transaction amount from the United States?",
            df,
            numeric(us_total, tol=0.5),
            category="messy_multi_step",
        ),
        EvalCase(
            "messy_q1_count",
            "How many transactions happened in Q1 (January–March) 2024? Dates are "
            "in several different formats.",
            df,
            numeric(q1_count),
            category="messy_dates",
        ),
    ]
