"""Fetch per-model token prices from OpenRouter for cost reporting."""

from __future__ import annotations

import json
import os
import urllib.request

_MODELS_URL = "https://openrouter.ai/api/v1/models"


def fetch_openrouter_prices(
    model_ids: list[str] | None = None,
    *,
    api_key: str | None = None,
) -> dict[str, tuple[float, float]]:
    """Return ``{model_id: (prompt_$/Mtok, completion_$/Mtok)}`` from OpenRouter.

    Pass these to `EvalReport.leaderboard` / `to_markdown` to add a cost column.

    Args:
        model_ids: Restrict to these ids; ``None`` returns all priced models.
        api_key: OpenRouter key; defaults to ``OPENROUTER_API_KEY``.

    Returns:
        Mapping of model id to ``(prompt_per_million, completion_per_million)``.
    """
    key = api_key or os.environ.get("OPENROUTER_API_KEY")
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    req = urllib.request.Request(_MODELS_URL, headers=headers)
    with urllib.request.urlopen(req) as resp:
        data = json.load(resp)["data"]

    wanted = set(model_ids) if model_ids is not None else None
    prices: dict[str, tuple[float, float]] = {}
    for model in data:
        mid = model.get("id")
        if wanted is not None and mid not in wanted:
            continue
        pricing = model.get("pricing", {})
        try:
            prompt = float(pricing.get("prompt", 0)) * 1_000_000
            completion = float(pricing.get("completion", 0)) * 1_000_000
        except (TypeError, ValueError):
            continue
        prices[mid] = (prompt, completion)
    return prices
