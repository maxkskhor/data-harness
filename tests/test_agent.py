"""Tests for the high-level `Agent` convenience class (PLAN_SDK Phase 1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from dataact.agent import Agent
from dataact.cache import SessionCache
from dataact.loop import Harness
from dataact.testing import FakeAdapter


def test_agent_is_exported_from_top_level_package():
    from dataact import Agent as TopLevelAgent
    from dataact.agent import Agent as ModuleAgent

    assert TopLevelAgent is ModuleAgent


class TestAgentPhase1:
    def test_run_returns_text(self, tmp_path):
        adapter = FakeAdapter([FakeAdapter.text("done")])
        agent = Agent(adapter=adapter, system="sys", run_dir=str(tmp_path))
        assert agent.run("hi") == "done"

    def test_default_tools_include_python_interpreter_and_list_variables(
        self, tmp_path
    ):
        adapter = FakeAdapter([FakeAdapter.text("done")])
        agent = Agent(adapter=adapter, system="sys", run_dir=str(tmp_path))
        agent.run("hi")
        tools_seen = adapter.calls[0]["tools"]
        names = {t.name for t in tools_seen}
        assert "python_interpreter" in names
        assert "list_variables" in names

    def test_run_is_one_shot_resets_history(self, tmp_path):
        adapter = FakeAdapter([FakeAdapter.text("first"), FakeAdapter.text("second")])
        agent = Agent(adapter=adapter, system="sys", run_dir=str(tmp_path))
        agent.run("hello")
        agent.run("again")
        # Each run should start with exactly one user message in the message list
        assert len(adapter.calls) == 2
        for call in adapter.calls:
            user_msgs = [m for m in call["messages"] if m.role == "user"]
            assert len(user_msgs) == 1

    def test_last_harness_points_to_most_recent(self, tmp_path):
        adapter = FakeAdapter([FakeAdapter.text("a"), FakeAdapter.text("b")])
        agent = Agent(adapter=adapter, system="sys", run_dir=str(tmp_path))
        assert agent.last_harness is None
        agent.run("one")
        first_h = agent.last_harness
        assert isinstance(first_h, Harness)
        agent.run("two")
        # A fresh harness is built per run; reference should change
        assert agent.last_harness is not first_h

    def test_last_run_file_set_after_run(self, tmp_path):
        adapter = FakeAdapter([FakeAdapter.text("done")])
        agent = Agent(adapter=adapter, system="sys", run_dir=str(tmp_path))
        assert agent.last_run_file is None
        agent.run("hi")
        assert agent.last_run_file is not None
        assert Path(agent.last_run_file).exists()
        assert Path(agent.last_run_file).suffix == ".jsonl"

    def test_cache_is_exposed(self, tmp_path):
        adapter = FakeAdapter([FakeAdapter.text("done")])
        agent = Agent(adapter=adapter, system="sys", run_dir=str(tmp_path))
        assert isinstance(agent.cache, SessionCache)

    def test_cache_can_be_passed_in(self, tmp_path):
        cache = SessionCache()
        cache.put("preloaded", [1, 2, 3])
        adapter = FakeAdapter([FakeAdapter.text("done")])
        agent = Agent(adapter=adapter, system="sys", cache=cache, run_dir=str(tmp_path))
        assert agent.cache is cache
        assert "preloaded" in agent.cache.list_handles()

    def test_run_dir_optional(self, tmp_path, monkeypatch):
        # When run_dir is omitted the Harness default is used. We don't want a
        # quick-start example to litter the tmp dir, so cd into tmp_path so the
        # default "./runs" lands somewhere disposable.
        monkeypatch.chdir(tmp_path)
        adapter = FakeAdapter([FakeAdapter.text("done")])
        agent = Agent(adapter=adapter, system="sys")
        agent.run("hi")
        runs = list((tmp_path / "runs").glob("*.jsonl"))
        assert len(runs) == 1

    def test_max_turns_propagates(self, tmp_path):
        adapter = FakeAdapter([FakeAdapter.text("done")])
        agent = Agent(adapter=adapter, system="sys", max_turns=7, run_dir=str(tmp_path))
        agent.run("hi")
        assert agent.last_harness._max_turns == 7

    def test_explain_returns_readable_sketch(self, tmp_path):
        adapter = FakeAdapter([FakeAdapter.text("done")])
        agent = Agent(adapter=adapter, system="sys", run_dir=str(tmp_path))
        sketch = agent.explain()
        assert isinstance(sketch, str)
        # Should mention the core primitives a reader needs to find
        assert "SessionCache" in sketch
        assert "python_interpreter" in sketch
        assert "list_variables" in sketch
        assert "Harness" in sketch

    def test_explain_works_without_running(self, tmp_path):
        adapter = FakeAdapter([])
        agent = Agent(adapter=adapter, system="sys", run_dir=str(tmp_path))
        # explain() must not require a prior run
        agent.explain()


class TestAgentPhase1OneShotInvariant:
    def test_second_run_does_not_see_first_run_messages(self, tmp_path):
        """Each Agent.run() builds a fresh Harness; messages must not leak across."""
        adapter = FakeAdapter([FakeAdapter.text("alpha"), FakeAdapter.text("beta")])
        agent = Agent(adapter=adapter, system="sys", run_dir=str(tmp_path))
        agent.run("first user prompt")
        agent.run("second user prompt")

        from dataact.types import TextBlock

        second_call_msgs = adapter.calls[1]["messages"]
        all_text = " ".join(
            b.text
            for m in second_call_msgs
            for b in m.content
            if isinstance(b, TextBlock)
        )
        assert "first user prompt" not in all_text
        assert "second user prompt" in all_text


def test_fake_adapter_drives_quickstart_snippet(tmp_path):
    """README quick-start should be runnable with a fake adapter (Phase 1 docs goal)."""
    adapter = FakeAdapter([FakeAdapter.text("The mean is 3.0")])
    agent = Agent(
        adapter=adapter,
        system="You are a data analyst.",
        run_dir=str(tmp_path),
    )
    result = agent.run("Compute the mean of [1, 2, 3, 4, 5].")
    assert result == "The mean is 3.0"


@pytest.mark.parametrize("n_runs", [1, 3])
def test_agent_run_count_matches_call_count(tmp_path, n_runs):
    adapter = FakeAdapter([FakeAdapter.text(f"r{i}") for i in range(n_runs)])
    agent = Agent(adapter=adapter, system="sys", run_dir=str(tmp_path))
    for i in range(n_runs):
        agent.run(f"msg {i}")
    assert len(adapter.calls) == n_runs
