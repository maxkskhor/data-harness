"""A harder suite that stretches the harness's strengths.

Unlike the bespoke suite (which capable models saturate), these tasks need:
- **joins** across several related DataFrame handles,
- **deep multi-step** reasoning (compute → filter → aggregate), and
- **stateful multi-turn conversations** that build on handles saved earlier
  (the `SessionCache` differentiator that single-shot benchmarks can't probe).

Ground-truth answers are computed by hand below; keep them in sync with the data.
"""

from __future__ import annotations

from data_harness.eval.case import ConversationCase, EvalCase, Turn
from data_harness.eval.graders import contains, numeric


def _customers():
    import pandas as pd

    return pd.DataFrame(
        {
            "customer_id": [1, 2, 3, 4, 5],
            "name": ["Ann", "Bob", "Cara", "Dan", "Eve"],
            "region": ["NA", "EU", "EU", "APAC", "NA"],
        }
    )


def _orders():
    import pandas as pd

    return pd.DataFrame(
        {
            "order_id": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            "customer_id": [1, 1, 2, 3, 2, 4, 5, 1, 3, 4],
            "product": [
                "Widget",
                "Gadget",
                "Widget",
                "Gizmo",
                "Gadget",
                "Widget",
                "Gizmo",
                "Widget",
                "Gadget",
                "Gizmo",
            ],
            "amount": [100, 200, 150, 300, 250, 120, 400, 90, 180, 350],
        }
    )


def _products():
    import pandas as pd

    return pd.DataFrame(
        {
            "product": ["Widget", "Gadget", "Gizmo"],
            "category": ["hardware", "hardware", "electronics"],
            "unit_cost": [40, 80, 150],
        }
    )


def _sales_db():
    return {
        "customers": _customers(),
        "orders": _orders(),
        "products": _products(),
    }


def _messy_orders():
    import pandas as pd

    return pd.DataFrame(
        {
            "order_id": [1, 2, 3, 3, 4, 5],
            "amount": [100.0, None, 150.0, 150.0, 200.0, None],
        }
    )


def hard_suite() -> list:
    """Hard multi-table, multi-step, and stateful multi-turn cases.

    Returns a mix of `EvalCase` (single-shot) and `ConversationCase` (multi-turn).
    """
    db = _sales_db()
    return [
        # --- joins across handles -----------------------------------------
        EvalCase(
            "join_top_region",
            "Join orders to customers and tell me which region has the highest "
            "total revenue.",
            db,
            contains("EU"),
            category="join",  # NA 790, EU 880, APAC 470
        ),
        EvalCase(
            "join_profit_category",
            "Join orders to products. Treating profit as amount minus unit_cost "
            "per order, which product category is most profitable?",
            db,
            contains("hardware"),
            category="join",  # hardware 690 vs elec 600
        ),
        # --- deep multi-step ----------------------------------------------
        EvalCase(
            "above_avg_combined",
            "Compute each customer's total spend. Among customers who spent above "
            "the average customer spend, what is their combined revenue?",
            db,
            numeric(950),
            category="multi_step",  # Cara 480 + Dan 470
        ),
        EvalCase(
            "pct_top_customer",
            "What percentage of total revenue comes from the highest-spending "
            "customer?",
            db,
            numeric(22.43, tol=0.5),
            category="multi_step",  # 480 / 2140
        ),
        EvalCase(
            "hardware_avg_order",
            "What is the average order amount for products in the hardware category?",
            db,
            numeric(155.71, tol=1.0),
            category="multi_step",  # 1090 / 7
        ),
        EvalCase(
            "median_order",
            "What is the median order amount across all orders?",
            db,
            numeric(190),
            category="multi_step",
        ),
        # --- stateful multi-turn (SessionCache) ---------------------------
        ConversationCase(
            "conv_customer_revenue",
            db,
            [
                Turn(
                    "Compute total revenue per customer by joining orders to "
                    "customers, and save it as `cust_rev`. How many customers are "
                    "there?",
                    numeric(5),
                ),
                Turn(
                    "Using cust_rev, which customer has the highest total revenue?",
                    contains("Cara"),  # 480
                ),
                Turn(
                    "What is the average total revenue across those customers?",
                    numeric(428, tol=0.5),  # 2140 / 5
                ),
            ],
            category="stateful",
        ),
        ConversationCase(
            "conv_clean_then_analyse",
            {"raw_orders": _messy_orders()},
            [
                Turn(
                    "Clean raw_orders: drop rows with a missing amount, then remove "
                    "duplicate order_ids (keep the first). Save it as `clean` and "
                    "tell me how many rows remain.",
                    numeric(3),  # rows 1, 3, 4
                ),
                Turn(
                    "Using clean, what is the total amount?",
                    numeric(450),  # 100 + 150 + 200
                ),
            ],
            category="stateful",
        ),
    ]
