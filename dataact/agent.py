"""High-level `Agent` convenience layer.

`Agent` is a thin composition over `Harness`, `SessionCache`, and the built-in
tools. It exists so the quick-start example reads cleanly. The low-level
primitives remain the canonical teaching surface — `agent.explain()` returns a
sketch of the equivalent explicit wiring.

`Agent.run()` is one-shot: each call builds a fresh `Harness` and starts with a
new message history. It is not a chat session.
"""

from __future__ import annotations

from pathlib import Path

from dataact.cache import SessionCache
from dataact.loop import Harness
from dataact.providers.base import ProviderAdapter
from dataact.tools.interpreter import PythonInterpreter
from dataact.tools.variables import make_list_variables_spec
from dataact.types import ToolSpec


class Agent:
    def __init__(
        self,
        adapter: ProviderAdapter,
        system: str,
        *,
        max_turns: int = 25,
        cache: SessionCache | None = None,
        run_dir: str | Path | None = None,
    ) -> None:
        self._adapter = adapter
        self._system = system
        self._max_turns = max_turns
        self._cache = cache if cache is not None else SessionCache()
        self._run_dir = run_dir
        self._last_harness: Harness | None = None
        self._last_run_file: str | None = None

    @property
    def cache(self) -> SessionCache:
        return self._cache

    @property
    def last_harness(self) -> Harness | None:
        return self._last_harness

    @property
    def last_run_file(self) -> str | None:
        return self._last_run_file

    def run(self, user_message: str) -> str:
        tools = self._build_tools()
        harness_kwargs: dict = {
            "adapter": self._adapter,
            "system": self._system,
            "tools": tools,
            "max_turns": self._max_turns,
            "cache": self._cache,
        }
        if self._run_dir is not None:
            harness_kwargs["run_dir"] = str(self._run_dir)

        harness = Harness(**harness_kwargs)
        self._last_harness = harness
        result = harness.run(user_message)
        # Newest jsonl in the run dir belongs to this run
        run_dir = Path(harness._run_dir)
        files = sorted(run_dir.glob("*.jsonl"), key=lambda f: f.stat().st_mtime)
        if files:
            self._last_run_file = str(files[-1])
        return result

    def explain(self) -> str:
        return _EXPLAIN_TEMPLATE.format(
            system=_truncate(self._system),
            max_turns=self._max_turns,
            run_dir=self._run_dir if self._run_dir is not None else "./runs",
        )

    def _build_tools(self) -> list[ToolSpec]:
        return [
            PythonInterpreter.make_tool_spec(self._cache),
            make_list_variables_spec(self._cache),
        ]


_EXPLAIN_TEMPLATE = """\
Agent is a thin composition layer. The equivalent explicit wiring is:

    from dataact.cache import SessionCache
    from dataact.loop import Harness
    from dataact.tools.interpreter import PythonInterpreter
    from dataact.tools.variables import make_list_variables_spec

    cache = SessionCache()
    tools = [
        PythonInterpreter.make_tool_spec(cache),
        make_list_variables_spec(cache),
    ]
    harness = Harness(
        adapter=adapter,
        system={system!r},
        tools=tools,
        max_turns={max_turns},
        run_dir={run_dir!r},
        cache=cache,
    )
    harness.run(user_message)

Each call to Agent.run() builds a fresh Harness with fresh tool specs.
Model-visible tools include python_interpreter and list_variables.
The message history resets per run; this is not a chat session.
"""


def _truncate(text: str, limit: int = 80) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"
