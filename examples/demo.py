"""
demo.py — Wires all five tools together with a synthetic OHLCV connector.

Requires ANTHROPIC_API_KEY to be set. Run:
    uv run python examples/demo.py
"""

from __future__ import annotations

import os
import sys

import pandas as pd

from dataact.cache import SessionCache
from dataact.loop import Harness
from dataact.tools.connectors import ConnectorRegistry
from dataact.tools.interpreter import PythonInterpreter
from dataact.tools.planner import Planner
from dataact.tools.subagent import make_subagent_spec
from dataact.tools.variables import make_list_variables_spec
from dataact.types import ToolSpec


def make_synthetic_ohlcv(n: int = 1000) -> pd.DataFrame:
    import datetime

    base = datetime.date(2024, 1, 1)
    return pd.DataFrame(
        {
            "date": [(base + datetime.timedelta(days=i)).isoformat() for i in range(n)],
            "open": [100.0 + i * 0.05 for i in range(n)],
            "high": [102.0 + i * 0.05 for i in range(n)],
            "low": [98.0 + i * 0.05 for i in range(n)],
            "close": [101.0 + i * 0.05 for i in range(n)],
            "volume": [10_000 + i * 10 for i in range(n)],
        }
    )


def main() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY not set. Skipping live demo.")
        sys.exit(0)

    from dataact.providers.anthropic import AnthropicAdapter

    session_cache = SessionCache(sample_size=5)

    # Build connector registry
    registry = ConnectorRegistry()
    registry.register(
        name="market_data",
        description="Synthetic OHLCV market data for demo purposes.",
        tools=[
            ToolSpec(
                name="market_data__fetch_ohlcv",
                description=(
                    "Fetch synthetic OHLCV data. Returns a DataFrame with 1000 rows."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Ticker symbol (ignored in synthetic mode)",
                        }
                    },
                },
                handler=lambda symbol="DEMO": make_synthetic_ohlcv(),
                visible=False,
            )
        ],
    )

    load_connectors_spec = registry.get_load_connectors_spec()
    wrapped_specs = registry.make_wrapped_specs(session_cache)

    # Planner
    planner = Planner()
    planner_specs = planner.make_tool_specs()

    # Interpreter
    interp_spec = PythonInterpreter.make_tool_spec(session_cache)

    # Variables
    variables_spec = make_list_variables_spec(session_cache)

    # Subagent
    def adapter_factory():
        return AnthropicAdapter(model="claude-haiku-4-5-20251001", max_tokens=2048)

    all_tools = (
        [load_connectors_spec, interp_spec, variables_spec]
        + planner_specs
        + wrapped_specs
    )

    subagent_spec = make_subagent_spec(
        adapter_factory=adapter_factory,
        parent_tools=all_tools,
        parent_cache=session_cache,
        run_dir="./runs",
    )
    all_tools.append(subagent_spec)

    # Main adapter
    adapter = AnthropicAdapter(model="claude-sonnet-4-6", max_tokens=4096)

    harness = Harness(
        adapter=adapter,
        system=(
            "You are a financial data analyst with access to market data tools. "
            "Use load_connectors to access data sources, "
            "python_interpreter to analyze data, "
            "and list_variables to check what's cached. "
            "Always produce a clear final answer."
        ),
        tools=all_tools,
        max_turns=10,
        run_dir="./runs",
        cache=session_cache,
    )

    # Register planner reminder
    harness.register_reminder(planner.reminder_hook)

    print("Starting agent-harness demo...")
    print("=" * 60)

    result = harness.run(
        "Load the market_data connector and fetch OHLCV data. "
        "Then compute the average closing price and the highest volume day. "
        "Summarize your findings."
    )

    print("\nFinal response:")
    print(result)

    from pathlib import Path

    run_files = list(Path("./runs").glob("*.jsonl"))
    if run_files:
        latest = max(run_files, key=lambda f: f.stat().st_mtime)
        print(f"\nJSONL log: {latest}")


if __name__ == "__main__":
    main()
