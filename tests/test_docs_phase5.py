"""Tests for Phase 5: documentation snippets importable, deterministic example.

TDD: written before implementation.
"""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path


class TestNewExportsFromPackage:
    def test_run_result_importable_from_top_level(self):
        from dataact import RunResult  # noqa: F401

    def test_usage_importable_from_top_level(self):
        from dataact import Usage  # noqa: F401

    def test_tool_annotations_importable_from_top_level(self):
        from dataact import ToolAnnotations  # noqa: F401

    def test_cache_storage_info_importable_from_top_level(self):
        from dataact import CacheStorageInfo  # noqa: F401


class TestInspectRunExample:
    def test_example_file_exists(self):
        example = Path("examples/inspect_run.py")
        assert example.exists(), "examples/inspect_run.py must exist"

    def test_example_runs_without_provider_keys(self):
        """The inspect_run example must work without any API keys."""
        spec = importlib.util.spec_from_file_location(
            "inspect_run_example",
            "examples/inspect_run.py",
        )
        assert spec is not None
        module = importlib.util.module_from_spec(spec)
        # Should not raise
        spec.loader.exec_module(module)  # type: ignore[union-attr]

    def test_example_produces_run_result(self):
        spec = importlib.util.spec_from_file_location(
            "inspect_run_example_result",
            "examples/inspect_run.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        from dataact import RunResult

        assert hasattr(module, "result")
        assert isinstance(module.result, RunResult)
