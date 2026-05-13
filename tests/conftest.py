"""Pytest configuration: auto-capture smoke test JSONL metadata after every
@live run and regenerate the HTML dashboard at session end.

Writes to smoke_results/latest.json and smoke_results/latest.html in the
project root after any session that contains at least one live test.
"""

from __future__ import annotations

import importlib.util
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

_INPUT_PRICE_PER_M = 0.15  # gpt-4o-mini
_OUTPUT_PRICE_PER_M = 0.60

_session_results: list[dict] = []
_session_start: float = 0.0
_PROJECT_ROOT = Path(__file__).parent.parent
_SMOKE_OUT = _PROJECT_ROOT / "smoke_results"


# ── pytest hooks ─────────────────────────────────────────────────────────────


def pytest_sessionstart(session: Any) -> None:
    global _session_start, _session_results
    _session_start = time.time()
    _session_results = []


@pytest.fixture(autouse=True)
def _smoke_capture_setup(request: pytest.FixtureRequest) -> Any:
    """Store tmp_path + start time on the node for harvest in makereport."""
    if not request.node.get_closest_marker("live"):
        yield
        return
    request.node._smoke_t0 = time.perf_counter()  # type: ignore[attr-defined]
    try:
        request.node._smoke_tmp_path = request.getfixturevalue("tmp_path")  # type: ignore[attr-defined]
    except pytest.FixtureLookupError:
        request.node._smoke_tmp_path = None  # type: ignore[attr-defined]
    yield


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo) -> Any:  # type: ignore[override]
    outcome = yield
    if call.when != "call" or not item.get_closest_marker("live"):
        return
    report = outcome.get_result()
    if report.skipped:
        return
    t0: float | None = getattr(item, "_smoke_t0", None)
    tmp_path: Path | None = getattr(item, "_smoke_tmp_path", None)
    elapsed_ms = (time.perf_counter() - t0) * 1000 if t0 is not None else 0.0
    record = _build_test_record(
        name=item.name,
        tmp_path=tmp_path,
        elapsed_ms=elapsed_ms,
        passed=report.passed,
        error=str(report.longrepr) if not report.passed else None,
    )
    _session_results.append(record)


def pytest_sessionfinish(session: Any, exitstatus: int) -> None:
    if not _session_results:
        return
    _SMOKE_OUT.mkdir(exist_ok=True)
    data = _build_session_data()
    (_SMOKE_OUT / "latest.json").write_text(json.dumps(data, indent=2))
    try:
        html = _load_dashboard_module().build_html(data)
        html_path = _SMOKE_OUT / "latest.html"
        html_path.write_text(html)
        print(f"\n  Smoke dashboard → {html_path}")
    except Exception as exc:
        print(f"\n  [smoke dashboard] HTML generation failed: {exc}")


# ── data builders ─────────────────────────────────────────────────────────────


def _build_session_data() -> dict:
    total_in = sum(h["input_tokens"] for t in _session_results for h in t["harnesses"])
    total_out = sum(
        h["output_tokens"] for t in _session_results for h in t["harnesses"]
    )
    passed = sum(1 for t in _session_results if t["status"] == "passed")
    return {
        "run_date": datetime.now(tz=timezone.utc).isoformat(),
        "model": "gpt-4o-mini",
        "pricing": {
            "input_per_m": _INPUT_PRICE_PER_M,
            "output_per_m": _OUTPUT_PRICE_PER_M,
        },
        "totals": {
            "tests": len(_session_results),
            "passed": passed,
            "failed": len(_session_results) - passed,
            "input_tokens": total_in,
            "output_tokens": total_out,
            "cost_usd": round(_cost(total_in, total_out), 6),
            "duration_ms": round((time.time() - _session_start) * 1000),
        },
        "tests": _session_results,
    }


def _build_test_record(
    name: str,
    tmp_path: Path | None,
    elapsed_ms: float,
    passed: bool,
    error: str | None,
) -> dict:
    harnesses: list[dict] = []
    if tmp_path is not None:
        for i, jf in enumerate(
            sorted(tmp_path.rglob("*.jsonl"), key=lambda p: p.stat().st_mtime)
        ):
            role = "main" if i == 0 else f"subagent_{i}"
            h = _parse_harness_jsonl(jf, role)
            if h:
                harnesses.append(h)

    total_in = sum(h["input_tokens"] for h in harnesses)
    total_out = sum(h["output_tokens"] for h in harnesses)
    return {
        "name": name,
        "short_name": name.removeprefix("test_openai_"),
        "status": "passed" if passed else "failed",
        "error": error,
        "duration_ms": round(elapsed_ms),
        "totals": {
            "turns": sum(h["turns"] for h in harnesses),
            "input_tokens": total_in,
            "output_tokens": total_out,
            "cost_usd": round(_cost(total_in, total_out), 6),
            "tool_calls": sum(h["tool_calls"] for h in harnesses),
            "tool_errors": sum(h["tool_errors"] for h in harnesses),
        },
        "harnesses": harnesses,
    }


def _parse_harness_jsonl(jsonl_path: Path, role: str) -> dict:
    try:
        records = [
            json.loads(line)
            for line in jsonl_path.read_text().splitlines()
            if line.strip()
        ]
    except Exception:
        return {}
    if not records:
        return {}

    # Reconstruct a flat chronological conversation from the cumulative
    # message history that the harness writes into every JSONL record.
    conversation: list[dict] = []
    prev_len = 0
    for rec in records:
        msgs = rec.get("messages", [])
        new_msgs = msgs[prev_len:]
        prev_len = len(msgs)
        metrics = rec.get("metrics", {})
        stop = rec.get("stop_reason", "")
        for msg in new_msgs:
            entry: dict = {"role": msg["role"], "content": msg.get("content", [])}
            if msg["role"] == "assistant":
                entry["turn_metrics"] = metrics
                entry["stop_reason"] = stop
            conversation.append(entry)

    total_in = sum(r.get("metrics", {}).get("input_tokens", 0) for r in records)
    total_out = sum(r.get("metrics", {}).get("output_tokens", 0) for r in records)
    tool_calls = sum(
        1
        for r in records
        for b in r.get("response_content", [])
        if b.get("type") == "tool_use"
    )
    return {
        "role": role,
        "turns": len(records),
        "input_tokens": total_in,
        "output_tokens": total_out,
        "latency_ms": round(
            sum(r.get("metrics", {}).get("latency_ms", 0) for r in records)
        ),
        "tool_calls": tool_calls,
        "tool_errors": sum(r.get("tool_error_count", 0) for r in records),
        "cost_usd": round(_cost(total_in, total_out), 6),
        "visible_tools": records[0].get("visible_tools", []),
        "system": records[0].get("system", ""),
        "tool_annotations": records[0].get("tool_annotations", {}),
        "conversation": conversation,
    }


def _cost(input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens * _INPUT_PRICE_PER_M / 1_000_000
        + output_tokens * _OUTPUT_PRICE_PER_M / 1_000_000
    )


def _load_dashboard_module() -> Any:
    here = Path(__file__).parent
    spec = importlib.util.spec_from_file_location(
        "_smoke_dashboard", here / "_smoke_dashboard.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod
