"""Tests for documented examples."""

from __future__ import annotations

from dataact.testing import FakeAdapter
from examples.quickstart import build_agent


def test_quickstart_build_agent_runs_with_fake_adapter(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    adapter = FakeAdapter([FakeAdapter.text("The mean is 3.0")])

    agent = build_agent(adapter)
    result = agent.run("Compute the mean of [1, 2, 3, 4, 5].")

    assert result == "The mean is 3.0"
