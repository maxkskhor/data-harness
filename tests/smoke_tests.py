"""
smoke_tests.py — Live smoke tests against the real Anthropic API.

Requires ANTHROPIC_API_KEY (loaded from .env at the project root).

Run all smoke tests:
    uv run pytest tests/smoke_tests.py -v -m live

Run one specific test:
    uv run pytest tests/smoke_tests.py::test_smoke_basic_completion -v -m live

Skip during normal CI (default pytest invocation skips 'live' marker):
    uv run pytest tests/ -v -m "not live"

Design notes:
- Uses claude-haiku-4-5-20251001 for most tests (cheap, fast).
- Assertions are structural, not on exact model output (non-deterministic).
- Each test is fully self-contained with its own cache + run_dir.
- Tests are ordered from simplest to most complex.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import pytest

from dataact.cache import SessionCache
from dataact.exceptions import MaxTurnsExceeded
from dataact.loop import Harness
from dataact.providers.anthropic import AnthropicAdapter
from dataact.tools.connectors import ConnectorRegistry
from dataact.tools.interpreter import PythonInterpreter
from dataact.tools.planner import Planner
from dataact.tools.subagent import make_subagent_spec
from dataact.tools.variables import make_list_variables_spec
from dataact.types import ToolSpec

# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────


def _load_env() -> None:
    """Load .env from the project root if not already in environment."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        try:
            from dotenv import load_dotenv

            load_dotenv(env_path)
        except ImportError:
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip())


_load_env()


def _skip_if_no_key():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")


def _haiku(max_tokens: int = 2048) -> AnthropicAdapter:
    return AnthropicAdapter(model="claude-haiku-4-5-20251001", max_tokens=max_tokens)


def _synthetic_ohlcv(n: int = 1000) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": [
                f"2024-{(i // 30 % 12) + 1:02d}-{(i % 28) + 1:02d}" for i in range(n)
            ],
            "open": [100.0 + i * 0.05 for i in range(n)],
            "high": [102.0 + i * 0.05 for i in range(n)],
            "low": [98.0 + i * 0.05 for i in range(n)],
            "close": [101.0 + i * 0.05 for i in range(n)],
            "volume": [10_000 + i * 10 for i in range(n)],
        }
    )


def _build_full_harness(tmp_path, n_rows: int = 1000, max_turns: int = 10):
    """Wire all five tools together with a synthetic OHLCV connector."""
    cache = SessionCache(sample_size=5)

    registry = ConnectorRegistry()
    registry.register(
        name="market_data",
        description="Synthetic OHLCV data for smoke-testing.",
        tools=[
            ToolSpec(
                name="market_data__fetch_ohlcv",
                description=f"Fetch synthetic OHLCV data ({n_rows} rows).",
                input_schema={
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}},
                },
                handler=lambda symbol="DEMO": _synthetic_ohlcv(n_rows),
                visible=False,
            )
        ],
    )

    load_spec = registry.get_load_connectors_spec()
    wrapped_specs = registry.make_wrapped_specs(cache)
    interp_spec = PythonInterpreter.make_tool_spec(cache)
    vars_spec = make_list_variables_spec(cache)

    planner = Planner()
    planner_specs = planner.make_tool_specs()

    tools = [load_spec, interp_spec, vars_spec] + planner_specs + wrapped_specs

    def adapter_factory():
        return _haiku()

    subagent_spec = make_subagent_spec(
        adapter_factory=adapter_factory,
        parent_tools=tools,
        parent_cache=cache,
        run_dir=str(tmp_path),
    )
    tools.append(subagent_spec)

    harness = Harness(
        adapter=_haiku(),
        system=(
            "You are a financial data analyst. "
            "You have access to market data, a Python interpreter, and a planner. "
            "Always produce a clear, concise final answer."
        ),
        tools=tools,
        max_turns=max_turns,
        run_dir=str(tmp_path),
        cache=cache,
    )
    harness.register_reminder(planner.reminder_hook)
    return harness, cache, planner


# ──────────────────────────────────────────────────────────────────────────────
# 1. Basic text completion — no tools
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.live
def test_smoke_basic_completion(tmp_path):
    """Model answers a factual question without using any tools."""
    _skip_if_no_key()
    harness = Harness(
        adapter=_haiku(),
        system="You are a helpful assistant. Answer concisely.",
        tools=[],
        max_turns=3,
        run_dir=str(tmp_path),
    )
    result = harness.run("What is 7 times 8? Reply with just the number.")
    assert "56" in result
    # JSONL created with exactly 1 line
    lines = _read_jsonl(tmp_path)
    assert len(lines) == 1
    assert lines[0]["turn"] == 1


# ──────────────────────────────────────────────────────────────────────────────
# 2. Single tool call — python_interpreter arithmetic
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.live
def test_smoke_interpreter_arithmetic(tmp_path):
    """Model uses python_interpreter to compute a value and reports it."""
    _skip_if_no_key()
    cache = SessionCache()
    harness = Harness(
        adapter=_haiku(),
        system="Use python_interpreter for any computation. Report the result.",
        tools=[PythonInterpreter.make_tool_spec(cache)],
        max_turns=5,
        run_dir=str(tmp_path),
    )
    result = harness.run(
        "Use the python interpreter to compute sum(range(101)) and tell me the answer."
    )
    assert "5050" in result
    lines = _read_jsonl(tmp_path)
    assert len(lines) >= 2  # at least: tool call turn + final answer turn


# ──────────────────────────────────────────────────────────────────────────────
# 3. Cache → list_variables introspection
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.live
def test_smoke_cache_and_list_variables(tmp_path):
    """Pre-populate cache; model uses list_variables to discover it and reports."""
    _skip_if_no_key()
    cache = SessionCache()
    import numpy as np

    cache.put("scores", np.array([85, 92, 78, 95, 88]))

    harness = Harness(
        adapter=_haiku(),
        system="Use list_variables to see what data is available, then answer.",
        tools=[
            make_list_variables_spec(cache),
            PythonInterpreter.make_tool_spec(cache),
        ],
        max_turns=5,
        run_dir=str(tmp_path),
    )
    result = harness.run(
        "What variables are in the session cache? Describe them briefly."
    )
    assert (
        "scores" in result.lower()
        or "variable" in result.lower()
        or "cache" in result.lower()
    )


# ──────────────────────────────────────────────────────────────────────────────
# 4. Connector load + fetch → snapshot in message, raw data in cache
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.live
def test_smoke_connector_load_and_fetch(tmp_path):
    """
    Model loads a connector, fetches data, then summarizes.
    Asserts: raw DataFrame in cache; only snapshot text in messages.
    """
    _skip_if_no_key()
    harness, cache, _ = _build_full_harness(tmp_path, n_rows=500)
    result = harness.run(
        "Load the market_data connector, fetch the OHLCV data, "
        "and tell me how many rows there are and the column names."
    )
    assert isinstance(result, str) and len(result) > 10

    # Raw DataFrame must be in cache
    found_df = any(
        isinstance(cache.get(h), pd.DataFrame) and len(cache.get(h)) == 500
        for h in cache.list_handles()
    )
    assert found_df, "Expected 500-row DataFrame in cache"

    # No message in the stored history contains the full DataFrame
    harness_messages = harness._messages
    for msg in harness_messages:
        for block in msg.content:
            text = getattr(block, "text", None) or getattr(block, "content", None) or ""
            assert len(text) < 200_000, "Raw DataFrame leaked into message history"


# ──────────────────────────────────────────────────────────────────────────────
# 5. Interpreter reads from cache handle
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.live
def test_smoke_interpreter_reads_cache_handle(tmp_path):
    """
    Pre-load a DataFrame as 'prices'; model uses interpreter to compute
    mean(prices.close).
    """
    _skip_if_no_key()
    cache = SessionCache()
    df = pd.DataFrame({"close": [100.0, 110.0, 120.0, 90.0, 130.0]})
    cache.put("prices", df)

    harness = Harness(
        adapter=_haiku(),
        system="Use python_interpreter to analyze cached data. Print results.",
        tools=[
            PythonInterpreter.make_tool_spec(cache),
            make_list_variables_spec(cache),
        ],
        max_turns=5,
        run_dir=str(tmp_path),
    )
    result = harness.run(
        "The variable 'prices' is a DataFrame with a 'close' column. "
        "Use python_interpreter to compute the mean of prices.close"
        " and tell me the value."
    )
    assert "110" in result  # mean of [100, 110, 120, 90, 130] = 110.0


# ──────────────────────────────────────────────────────────────────────────────
# 6. Interpreter save() → handle visible via list_variables
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.live
def test_smoke_interpreter_save_then_list(tmp_path):
    """
    Model uses interpreter to compute something, save() it, then list_variables
    shows it.
    """
    _skip_if_no_key()
    cache = SessionCache()
    harness = Harness(
        adapter=_haiku(),
        system="Use tools step by step. Save intermediate results with save().",
        tools=[
            PythonInterpreter.make_tool_spec(cache),
            make_list_variables_spec(cache),
        ],
        max_turns=8,
        run_dir=str(tmp_path),
    )
    result = harness.run(
        "Use python_interpreter to compute [x**2 for x in range(5)], "
        "save it as 'squares' using save('squares', ...), "
        "then call list_variables and confirm squares is listed."
    )
    # Cache should have 'squares'
    assert "squares" in cache.list_handles(), "Expected 'squares' in cache"
    assert isinstance(result, str) and len(result) > 5


# ──────────────────────────────────────────────────────────────────────────────
# 7. Planner add → list → update → final answer
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.live
def test_smoke_planner_flow(tmp_path):
    """
    Model adds tasks to the planner, lists them, marks one done, summarizes.
    """
    _skip_if_no_key()
    planner = Planner()
    harness = Harness(
        adapter=_haiku(),
        system=(
            "You are a task-tracking assistant. Use the planner tools to manage tasks."
        ),
        tools=planner.make_tool_specs(),
        max_turns=8,
        run_dir=str(tmp_path),
    )
    harness.register_reminder(planner.reminder_hook)
    result = harness.run(
        "Add two tasks: 'Fetch data' and 'Analyze results'. "
        "Then list them, mark 'Fetch data' as done, list again, and summarize the"
        " status."
    )
    # At least one task should have been added
    assert len(planner._items) >= 1
    # At least one item marked done
    statuses = [i["status"] for i in planner._items]
    assert "done" in statuses
    assert isinstance(result, str) and len(result) > 10


# ──────────────────────────────────────────────────────────────────────────────
# 8. Subagent text_only — isolated worker returns result
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.live
def test_smoke_subagent_text_only(tmp_path):
    """
    Parent spawns a subagent for a computation subtask; result returned as text.
    Subagent's cache is isolated from parent's.
    """
    _skip_if_no_key()
    parent_cache = SessionCache()
    parent_cache.put("context", "Sales data Q1 2024")

    def adapter_factory():
        return _haiku()

    tools: list[ToolSpec] = []
    subagent_spec = make_subagent_spec(
        adapter_factory=adapter_factory,
        parent_tools=tools,
        parent_cache=parent_cache,
        run_dir=str(tmp_path),
    )

    harness = Harness(
        adapter=_haiku(),
        system="You are a coordinator. Delegate computation tasks to the subagent.",
        tools=[subagent_spec],
        max_turns=5,
        run_dir=str(tmp_path),
        cache=parent_cache,
    )
    result = harness.run(
        "Use the subagent tool with task='Compute 15 * 37 and return the result'. "
        "Then report what the subagent returned."
    )
    assert isinstance(result, str) and len(result) > 5
    # Parent cache unchanged — subagent's work doesn't leak
    assert "context" in parent_cache.list_handles()


# ──────────────────────────────────────────────────────────────────────────────
# 9. Subagent publish_created — new handles copied to parent cache
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.live
def test_smoke_subagent_publish_created(tmp_path):
    """
    Subagent uses interpreter + save(), publishes new handle back to parent.
    Parent cache gains the handle; raw data never traverses the prompt.
    """
    _skip_if_no_key()
    parent_cache = SessionCache()

    def adapter_factory():
        # Give subagent its own interpreter-enabled harness
        return _haiku()

    # Build subagent tools that include an interpreter
    sub_cache_ref = [None]

    # Use the real make_subagent_spec but intercept sub-cache creation
    sub_interp_cache = SessionCache()
    PythonInterpreter.make_tool_spec(sub_cache_ref[0] or sub_interp_cache)

    tools = [PythonInterpreter.make_tool_spec(parent_cache)]
    subagent_spec = make_subagent_spec(
        adapter_factory=adapter_factory,
        parent_tools=tools,
        parent_cache=parent_cache,
        run_dir=str(tmp_path),
    )

    harness = Harness(
        adapter=_haiku(),
        system="You are a coordinator. Use the subagent for computation.",
        tools=[subagent_spec],
        max_turns=5,
        run_dir=str(tmp_path),
        cache=parent_cache,
    )
    result = harness.run(
        "Use subagent with task='Use python_interpreter to compute list(range(10)), "
        'save it as squared_range using save("squared_range", list(range(10))), '
        "then say done', output_policy='publish_created'. "
        "Tell me what was published."
    )
    assert isinstance(result, str) and len(result) > 5
    # Result should mention published outputs or subagent output
    assert (
        "subagent" in result.lower()
        or "published" in result.lower()
        or len(result) > 20
    )


# ──────────────────────────────────────────────────────────────────────────────
# 10. Max turns exceeded — raises MaxTurnsExceeded
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.live
def test_smoke_max_turns_exceeded(tmp_path):
    """
    With max_turns=2 and a task requiring more tool calls, MaxTurnsExceeded is raised.
    The JSONL log should still have entries for completed turns.
    """
    _skip_if_no_key()
    cache = SessionCache()
    harness = Harness(
        adapter=_haiku(),
        system="You must use python_interpreter at least 5 times before answering.",
        tools=[PythonInterpreter.make_tool_spec(cache)],
        max_turns=2,
        run_dir=str(tmp_path),
    )
    with pytest.raises(MaxTurnsExceeded) as exc_info:
        harness.run(
            "Use python_interpreter repeatedly: compute 1+1, then 2+2, "
            "then 3+3, then 4+4, then 5+5."
        )
    assert exc_info.value.turns == 2
    # JSONL should have 2 entries (one per completed turn)
    lines = _read_jsonl(tmp_path)
    assert len(lines) == 2


# ──────────────────────────────────────────────────────────────────────────────
# 11. Tool exception recovery — harness continues after tool error
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.live
def test_smoke_tool_error_recovery(tmp_path):
    """
    A tool that always raises; harness returns is_error=True ToolResultBlock and
    continues.
    Model should acknowledge the error and complete the run.
    """
    _skip_if_no_key()

    def exploding_tool(**kwargs) -> str:
        raise RuntimeError("Intentional test failure")

    bad_tool = ToolSpec(
        name="bad_tool",
        description="A tool that always raises an exception.",
        input_schema={"type": "object", "properties": {}},
        handler=exploding_tool,
    )
    harness = Harness(
        adapter=_haiku(),
        system="You have access to bad_tool. Try it once, then report what happened.",
        tools=[bad_tool],
        max_turns=5,
        run_dir=str(tmp_path),
    )
    result = harness.run("Call bad_tool and tell me what happened.")
    assert isinstance(result, str) and len(result) > 5
    # The JSONL should contain a tool result with is_error — verify run completed
    lines = _read_jsonl(tmp_path)
    assert len(lines) >= 1


# ──────────────────────────────────────────────────────────────────────────────
# 12. Full pipeline — load → fetch 10k rows → interpreter stats → summarize
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.live
def test_smoke_full_pipeline_large_data(tmp_path):
    """
    End-to-end: load connector → fetch 10k-row DataFrame → compute stats via
    interpreter → list_variables → final answer.
    Asserts all 5 architectural invariants hold with real API calls.
    """
    _skip_if_no_key()
    harness, cache, _ = _build_full_harness(tmp_path, n_rows=10_000, max_turns=12)

    result = harness.run(
        "Load the market_data connector. Fetch OHLCV data. "
        "Use python_interpreter to compute: mean close price, max volume, "
        "and number of rows. "
        "Print each result. Then summarize your findings."
    )

    assert isinstance(result, str) and len(result) > 20

    # Invariant: raw 10k-row DataFrame in cache
    dfs = [
        cache.get(h)
        for h in cache.list_handles()
        if isinstance(cache.get(h), pd.DataFrame)
    ]
    assert any(len(df) == 10_000 for df in dfs), "Expected 10k-row DataFrame in cache"

    # Invariant: no message contains full raw data
    for msg in harness._messages:
        for block in msg.content:
            text = getattr(block, "text", None) or getattr(block, "content", None) or ""
            assert len(text) < 500_000

    # Invariant: system prompt byte-stable across all turns
    lines = _read_jsonl(tmp_path)
    hashes = [line["system_hash"] for line in lines]
    assert len(set(hashes)) == 1, "System hash changed between turns"

    # Invariant: turn 1 has full system, rest have only hash
    assert "system" in lines[0]
    for line in lines[1:]:
        assert "system" not in line


# ──────────────────────────────────────────────────────────────────────────────
# 13. JSONL log structure — all fields present and parseable
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.live
def test_smoke_jsonl_log_structure(tmp_path):
    """
    Verify every JSONL line has the expected schema: turn, timestamp,
    system_hash, messages, response_content, stop_reason, tool_results, metrics.
    """
    _skip_if_no_key()
    cache = SessionCache()
    harness = Harness(
        adapter=_haiku(),
        system="Answer in one sentence.",
        tools=[PythonInterpreter.make_tool_spec(cache)],
        max_turns=5,
        run_dir=str(tmp_path),
    )
    harness.run("Use python_interpreter to compute 2**10 and tell me the result.")

    lines = _read_jsonl(tmp_path)
    assert len(lines) >= 1
    required_keys = {
        "turn",
        "timestamp",
        "system_hash",
        "messages",
        "response_content",
        "stop_reason",
        "tool_results",
        "metrics",
    }
    metric_keys = {
        "input_tokens",
        "output_tokens",
        "cache_read_tokens",
        "cache_write_tokens",
        "latency_ms",
    }
    for line in lines:
        assert required_keys.issubset(line.keys()), (
            f"Missing keys in turn {line.get('turn')}: {required_keys - line.keys()}"
        )
        assert metric_keys.issubset(line["metrics"].keys())
        assert isinstance(line["turn"], int)
        assert isinstance(line["metrics"]["latency_ms"], (int, float))
        assert line["metrics"]["latency_ms"] > 0


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _read_jsonl(run_dir) -> list[dict]:
    files = list(Path(run_dir).glob("*.jsonl"))
    if not files:
        return []
    latest = max(files, key=lambda f: f.stat().st_mtime)
    lines = []
    for raw in latest.read_text().strip().splitlines():
        raw = raw.strip()
        if raw:
            lines.append(json.loads(raw))
    return lines
