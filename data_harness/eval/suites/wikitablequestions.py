"""Public benchmark loader: WikiTableQuestions (table QA).

Each example is a table + a natural-language question + accepted answers. We load
the table as a DataFrame and grade with ``contains`` against the accepted
answers. Requires the ``[eval]`` extra (``datasets``); the row→case conversion is
factored out so it can be unit-tested without the download.
"""

from __future__ import annotations

from typing import Any

from data_harness.eval.case import EvalCase
from data_harness.eval.graders import contains


def wtq_row_to_case(index: int, row: dict[str, Any]) -> EvalCase:
    """Convert one WikiTableQuestions row into an `EvalCase`.

    Args:
        index: Row index, used to build a stable case id.
        row: A dataset row with ``question``, ``answers`` (list[str]) and
            ``table`` (``{"header": [...], "rows": [[...], ...]}``).
    """
    import pandas as pd

    table = row["table"]
    df = pd.DataFrame(table["rows"], columns=table["header"])
    return EvalCase(
        id=f"wtq-{index}",
        question=row["question"],
        data=df,
        grader=contains(list(row["answers"])),
        category="wtq",
        tags=("public", "table-qa"),
    )


def load_wikitablequestions(
    split: str = "validation",
    limit: int | None = 50,
    *,
    seed: int = 0,
) -> list[EvalCase]:
    """Load WikiTableQuestions cases from Hugging Face ``datasets``.

    Args:
        split: Dataset split (``"validation"``, ``"test"``, ``"train"``).
        limit: Cap the number of cases (``None`` for all).
        seed: Shuffle seed for reproducible sampling when ``limit`` is set.

    Returns:
        A list of `EvalCase`.

    Raises:
        RuntimeError: If the ``datasets`` package is not installed.
    """
    try:
        from datasets import load_dataset
    except ImportError as exc:  # pragma: no cover - install-matrix dependent
        raise RuntimeError(
            "WikiTableQuestions requires the 'eval' extra: pip install "
            "'data-harness[eval]'."
        ) from exc

    ds = load_dataset("wikitablequestions", split=split)
    if limit is not None:
        ds = ds.shuffle(seed=seed).select(range(min(limit, len(ds))))
    return [wtq_row_to_case(i, row) for i, row in enumerate(ds)]
