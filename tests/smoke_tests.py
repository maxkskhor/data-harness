"""Reusable live smoke tests for the released SDK surface.

These tests call the real OpenAI API and are intentionally excluded from normal
unit-test runs. They cover the quick SDK path, explicit harness wiring, real
checked-in data, connector/cache behaviour, subagents, and JSONL logs.

Required:
    OPENAI_API_KEY

Optional:
    DATAACT_OPENAI_SMOKE_MODEL=gpt-4o-mini

Run:
    uv run pytest tests/smoke_tests.py -v -m live

The default model is OpenAI's cheap mini model used by the adapter examples.
Override DATAACT_OPENAI_SMOKE_MODEL when you want to compare another model.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import pytest

from dataact import Agent
from dataact.cache import SessionCache
from dataact.loop import Harness
from dataact.providers.openai import OpenAIAdapter
from dataact.tools.planner import Planner
from dataact.tools.subagent import make_subagent_spec
from dataact.types import ToolSpec
from examples.advanced_wiring import build_base_tools, load_unemployment_rate

pytestmark = pytest.mark.live

DEFAULT_OPENAI_SMOKE_MODEL = "gpt-4o-mini"


def _load_env() -> None:
    if os.environ.get("OPENAI_API_KEY"):
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(Path(__file__).parent.parent / ".env")


def _require_openai_key() -> None:
    _load_env()
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set")


def _openai(max_tokens: int = 512) -> OpenAIAdapter:
    model = os.environ.get("DATAACT_OPENAI_SMOKE_MODEL", DEFAULT_OPENAI_SMOKE_MODEL)
    return OpenAIAdapter(model=model, max_tokens=max_tokens)


def _latest_jsonl(run_dir: Path) -> list[dict]:
    files = sorted(run_dir.glob("*.jsonl"), key=lambda path: path.stat().st_mtime)
    assert files, f"No JSONL run logs found in {run_dir}"
    return [json.loads(line) for line in files[-1].read_text().splitlines() if line]


def _all_text_from_messages(harness: Harness) -> str:
    parts: list[str] = []
    for message in harness._messages:
        for block in message.content:
            text = getattr(block, "text", None) or getattr(block, "content", None)
            if text:
                parts.append(text)
    return "\n".join(parts)


def test_openai_basic_harness_completion(tmp_path):
    _require_openai_key()
    harness = Harness(
        adapter=_openai(max_tokens=64),
        system="Answer concisely.",
        tools=[],
        max_turns=2,
        run_dir=str(tmp_path),
    )

    result = harness.run("What is 7 times 8? Reply with only the number.")

    assert "56" in result
    lines = _latest_jsonl(tmp_path)
    assert len(lines) == 1
    assert lines[0]["stop_reason"] == "end_turn"
    assert lines[0]["metrics"]["input_tokens"] > 0


def test_openai_agent_can_ask_clarifying_question(tmp_path):
    _require_openai_key()
    agent = Agent(
        adapter=_openai(max_tokens=128),
        system=(
            "You are a careful data analyst. If the request lacks the dataset or "
            "metric needed for analysis, ask one concise clarifying question and "
            "do not use tools."
        ),
        max_turns=2,
        run_dir=str(tmp_path),
    )

    result = agent.run("Analyse the macro data for me.")

    assert "?" in result
    assert agent.last_harness is not None
    assert all(not line["tool_results"] for line in _latest_jsonl(tmp_path))


def test_openai_agent_simple_sdk_uses_python_and_saves_handle(tmp_path):
    _require_openai_key()
    agent = Agent(
        adapter=_openai(max_tokens=384),
        system=(
            "You are validating an SDK. Use python_interpreter for arithmetic. "
            "When the user gives exact Python code, pass that code to the tool "
            "unchanged."
        ),
        max_turns=6,
        run_dir=str(tmp_path),
    )

    result = agent.run(
        "Call python_interpreter with exactly this code:\n"
        "value = sum([1, 2, 3, 4, 5])\n"
        "save('total_sum', value)\n"
        "print(value)\n"
        "Then answer with the numeric value."
    )

    assert "15" in result
    assert agent.cache.get("total_sum") == 15
    assert agent.last_run_file is not None
    lines = _latest_jsonl(tmp_path)
    assert any(line["tool_results"] for line in lines)


def test_openai_agent_connector_real_fred_data(tmp_path):
    _require_openai_key()
    agent = Agent(
        adapter=_openai(max_tokens=768),
        system=(
            "You are a macro data analyst. Load connectors before using their "
            "tools. The connector snapshot is incomplete sample text; never "
            "reconstruct data from it. Use python_interpreter against the cached "
            "DataFrame handle named load_unemployment_rate."
        ),
        max_turns=8,
        run_dir=str(tmp_path),
    )

    macro = agent.connector(
        "macro_data",
        description="Checked-in FRED unemployment-rate sample.",
    )
    macro.tool(
        load_unemployment_rate,
        description="Load monthly 2024 FRED UNRATE observations as a DataFrame.",
    )

    result = agent.run(
        "Load macro_data, call load_unemployment_rate for UNRATE, then call "
        "python_interpreter with code equivalent to:\n"
        "df = load_unemployment_rate\n"
        "summary = {\n"
        "    'row_count': len(df),\n"
        "    'average': round(float(df['value'].mean()), 3),\n"
        "    'highest_date': str(df.loc[df['value'].idxmax(), 'date'].date()),\n"
        "    'highest_value': float(df['value'].max()),\n"
        "}\n"
        "save('unrate_summary', summary)\n"
        "print(summary)\n"
        "Final answer must include row_count, average, highest_date, and "
        "highest_value."
    )

    assert isinstance(result, str) and result

    df = agent.cache.get("load_unemployment_rate")
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 12
    assert round(float(df["value"].mean()), 3) == 4.033
    highest = df.loc[df["value"].idxmax()]
    assert str(highest["date"].date()) == "2024-07-01"
    assert float(highest["value"]) == 4.3


def test_openai_explicit_harness_real_data_planner_and_subagent(tmp_path):
    _require_openai_key()
    cache = SessionCache(sample_size=4)
    planner = Planner()
    base_tools = build_base_tools(cache)
    tools = base_tools + planner.make_tool_specs()

    subagent_spec = make_subagent_spec(
        adapter_factory=lambda: _openai(max_tokens=512),
        parent_tools=base_tools,
        parent_cache=cache,
        run_dir=str(tmp_path),
        make_sub_tools=build_base_tools,
    )
    tools.append(subagent_spec)

    harness = Harness(
        adapter=_openai(max_tokens=1024),
        system=(
            "You are validating explicit dataact harness wiring. Use the planner "
            "for a short checklist, load macro_data, use Python for aggregate "
            "calculations, and use a subagent for the highest-month check."
        ),
        tools=tools,
        max_turns=12,
        run_dir=str(tmp_path),
        cache=cache,
    )
    harness.register_reminder(planner.reminder_hook)

    result = harness.run(
        "Add a plan item for loading UNRATE and another for analysing it. "
        "Load macro_data, load the UNRATE sample, compute the average value in "
        "Python, then ask a subagent with the cached data handle to identify the "
        "highest unemployment month. Final answer must include the average and "
        "highest month/value."
    )

    assert isinstance(result, str) and result
    assert len(planner._items) >= 2

    df = cache.get("load_unemployment_rate")
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 12
    assert round(float(df["value"].mean()), 3) == 4.033
    highest = df.loc[df["value"].idxmax()]
    assert str(highest["date"].date()) == "2024-07-01"
    assert float(highest["value"]) == 4.3

    lines = _latest_jsonl(tmp_path)
    tool_names = [
        block["name"]
        for line in lines
        for block in line["response_content"]
        if block.get("type") == "tool_use"
    ]
    assert "planner__add" in tool_names
    assert "subagent" in tool_names
    assert len({line["system_hash"] for line in lines}) == 1
    assert "system" in lines[0]
    assert all("system" not in line for line in lines[1:])
    assert any("load_unemployment_rate" in line["cache_storage"] for line in lines)


def test_openai_disk_backed_cache_keeps_raw_data_out_of_messages(tmp_path):
    _require_openai_key()
    cache = SessionCache(sample_size=3, storage_dir=tmp_path / "cache", hot_limit=1)
    tools = build_base_tools(cache)
    harness = Harness(
        adapter=_openai(max_tokens=768),
        system=(
            "Use macro_data and python_interpreter. Do not paste raw tables; "
            "summarise the cached handles."
        ),
        tools=tools,
        max_turns=8,
        run_dir=str(tmp_path / "runs"),
        cache=cache,
    )

    result = harness.run(
        "Load macro_data, load UNRATE, save a separate Python summary dict named "
        "unrate_summary with row_count, average, and max_value, then answer."
    )

    assert "unrate_summary" in cache.handle_names()
    assert any(meta["location"] == "disk" for meta in cache.storage_metadata().values())
    assert all("path" not in meta for meta in cache.storage_metadata().values())
    assert "12" in result

    message_text = _all_text_from_messages(harness)
    assert "2024-01-01,UNRATE,3.7" not in message_text
    assert len(message_text) < 30_000


def test_openai_tool_error_is_reported_and_logged(tmp_path):
    _require_openai_key()

    def failing_tool() -> str:
        raise RuntimeError("intentional smoke failure")

    bad_tool = ToolSpec(
        name="bad_tool",
        description="A tool that always raises RuntimeError.",
        input_schema={"type": "object", "properties": {}},
        handler=failing_tool,
    )
    harness = Harness(
        adapter=_openai(max_tokens=256),
        system="Call bad_tool exactly once, then explain that it failed.",
        tools=[bad_tool],
        max_turns=4,
        run_dir=str(tmp_path),
    )

    result = harness.run("Call bad_tool once and report the error.")

    assert "fail" in result.lower() or "error" in result.lower()
    tool_results = [
        block for line in _latest_jsonl(tmp_path) for block in line["tool_results"]
    ]
    assert any(block["is_error"] for block in tool_results)
