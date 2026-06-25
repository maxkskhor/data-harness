"""A suite that stresses the handle/snapshot design with large data.

The model never sees the raw rows — only a compact snapshot (shape + a few
sample rows). Answering therefore *requires* computing over the full DataFrame
via the interpreter handle; you cannot eyeball the answer, and a naive approach
that tried to read the data into the prompt would blow the context window.

Includes a **snapshot trap**: the few sample rows in the snapshot are
deliberately misleading, so a model that answers from the snapshot instead of
running code on the handle gets it wrong.

Ground truth is computed here from the same seeded data, so graders stay exact.
"""

from __future__ import annotations

from data_harness.eval.case import EvalCase
from data_harness.eval.graders import contains, numeric

_N = 100_000
_REGIONS = ["NA", "EU", "APAC", "LATAM", "MEA"]


def _large_sales(seed: int = 0, n: int = _N):
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "txn_id": np.arange(n),
            "region": rng.choice(_REGIONS, n, p=[0.30, 0.25, 0.20, 0.15, 0.10]),
            "year": rng.choice([2023, 2024], n),
            "amount": rng.integers(10, 1000, n),
        }
    )


def _snapshot_trap(seed: int = 1, n: int = 50_000):
    """First rows look like EU dominates; the full data is dominated by NA."""
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(seed)
    decoy = pd.DataFrame({"region": ["EU"] * 5, "amount": [100_000] * 5})
    bulk = pd.DataFrame(
        {
            "region": rng.choice(["NA", "EU", "APAC"], n, p=[0.8, 0.1, 0.1]),
            "amount": rng.integers(1, 100, n),
        }
    )
    return pd.concat([decoy, bulk], ignore_index=True)


def large_data_suite() -> list[EvalCase]:
    """Cases over large frames that can only be answered via the handle."""
    sales = _large_sales()
    trap = _snapshot_trap()

    total = int(sales["amount"].sum())
    over_500 = int((sales["amount"] > 500).sum())
    top_region = sales.groupby("region")["amount"].sum().idxmax()
    na_2024_avg = float(
        sales[(sales["region"] == "NA") & (sales["year"] == 2024)]["amount"].mean()
    )
    trap_top = trap.groupby("region")["amount"].sum().idxmax()

    return [
        EvalCase(
            "large_total",
            f"The table has {len(sales):,} rows. What is the total amount across "
            "all transactions?",
            sales,
            numeric(total),
            category="large_agg",
        ),
        EvalCase(
            "large_count_over_500",
            "How many transactions have an amount greater than 500?",
            sales,
            numeric(over_500),
            category="large_filter",
        ),
        EvalCase(
            "large_top_region",
            "Which region has the highest total amount?",
            sales,
            contains(top_region),
            category="large_groupby",
        ),
        EvalCase(
            "large_na_2024_avg",
            "What is the average amount for region NA in year 2024?",
            sales,
            numeric(na_2024_avg, tol=0.5),
            category="large_multi_step",
        ),
        EvalCase(
            "snapshot_trap_top_region",
            "Which region has the highest total amount? Be careful to compute over "
            "all rows, not just the first few.",
            trap,
            contains(trap_top),
            category="snapshot_trap",
        ),
    ]
