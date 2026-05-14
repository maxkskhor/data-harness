"""High-level `Agent` and `AsyncAgent` convenience layers.

`Agent` wraps `Harness` for sync workflows.
`AsyncAgent` wraps `AsyncHarness` for async and streaming workflows.

Both are one-shot per `run()` call. Use `session()` / `async_session()` for
multi-turn conversations over a shared message history and cache.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from data_harness.cache import SessionCache
from data_harness.loop import AsyncHarness, Harness
from data_harness.providers.base import AsyncProviderAdapter, ProviderAdapter
from data_harness.result import RunResult
from data_harness.schema import infer_input_schema
from data_harness.streaming import StreamEvent
from data_harness.tools.connectors import ConnectorRegistry
from data_harness.tools.interpreter import PythonInterpreter
from data_harness.tools.planner import Planner
from data_harness.tools.subagent import _copy_cache_value, make_subagent_spec
from data_harness.tools.variables import make_list_variables_spec
from data_harness.types import ToolAnnotations, ToolSpec


@dataclass(frozen=True)
class _ConnectorToolDefinition:
    connector_name: str
    fn: Callable[..., Any]
    description: str
    input_schema: dict
    annotations: ToolAnnotations | None = None


@dataclass(frozen=True)
class _ConnectorDefinition:
    name: str
    description: str


class ConnectorBuilder:
    """Fluent builder for attaching tools to a named connector on an `Agent`.

    Obtain an instance via `Agent.connector` rather than constructing directly.
    """

    def __init__(self, agent: Agent | AsyncAgent, name: str) -> None:
        self._agent = agent
        self._name = name

    def tool(
        self,
        fn: Callable[..., Any],
        *,
        description: str,
        input_schema: dict | None = None,
        annotations: ToolAnnotations | None = None,
    ) -> Callable[..., Any]:
        """Register ``fn`` as a tool under this connector.

        Args:
            fn: The callable to expose as a tool. Its name becomes the tool
                name (prefixed with the connector name).
            description: Natural-language description shown to the model.
            input_schema: JSON Schema for the tool's parameters. Inferred from
                ``fn``'s type annotations when ``None``.
            annotations: Optional `ToolAnnotations` side-effect hints.

        Returns:
            ``fn`` unchanged, so the method can be used as a decorator.
        """
        schema = input_schema if input_schema is not None else infer_input_schema(fn)
        self._agent._connector_tools.append(
            _ConnectorToolDefinition(
                connector_name=self._name,
                fn=fn,
                description=description,
                input_schema=schema,
                annotations=annotations,
            )
        )
        return fn


def _build_tools_for(
    agent: Agent | AsyncAgent,
    *,
    planner: Planner | None,
    cache: SessionCache,
) -> list[ToolSpec]:
    """Shared tool-building logic for Agent and AsyncAgent."""
    tools = [
        PythonInterpreter.make_tool_spec(cache),
        make_list_variables_spec(cache),
    ]
    if planner is not None:
        tools.extend(planner.make_tool_specs())
    if agent._connectors:
        registry = ConnectorRegistry()
        for connector_name, connector in agent._connectors.items():
            registry.register(
                name=connector_name,
                description=connector.description,
                tools=[
                    ToolSpec(
                        name=f"{connector_name}__{definition.fn.__name__}",
                        description=definition.description,
                        input_schema=definition.input_schema,
                        handler=definition.fn,
                        visible=False,
                        annotations=definition.annotations,
                    )
                    for definition in agent._connector_tools
                    if definition.connector_name == connector_name
                ],
            )
        tools.append(registry.get_load_connectors_spec())
        tools.extend(registry.make_wrapped_specs(cache))
    return tools


class Agent:
    """High-level synchronous agent.

    `Agent` composes a `Harness`, a `SessionCache`, and optional tools from a
    single configuration. Each call to `run` builds a fresh `Harness` with a
    fresh message history. Use `session` when you need multi-turn conversation
    state to persist across questions.

    Example::

        from data_harness import Agent
        from data_harness.providers.anthropic import AnthropicAdapter

        agent = Agent(
            adapter=AnthropicAdapter(model="claude-sonnet-4-6"),
            system="You are a data analyst.",
        )
        print(agent.run("Compute the mean of [1, 2, 3]."))

    Args:
        adapter: Synchronous provider adapter.
        system: System prompt passed unchanged to every `Harness` run.
        max_turns: Hard cap on provider turns per `run` call.
        cache: Shared `SessionCache`. A fresh cache is created when ``None``.
        run_dir: Directory for JSONL logs. Defaults to ``./runs``.
    """

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
        self._connectors: dict[str, _ConnectorDefinition] = {}
        self._connector_tools: list[_ConnectorToolDefinition] = []
        self._planner_enabled = False
        self._subagent_factory: Callable[[], ProviderAdapter] | None = None

    @property
    def cache(self) -> SessionCache:
        return self._cache

    @property
    def last_harness(self) -> Harness | None:
        return self._last_harness

    @property
    def last_run_file(self) -> str | None:
        return self._last_run_file

    def connector(self, name: str, *, description: str) -> ConnectorBuilder:
        """Register a named connector and return a builder for attaching tools.

        Connector tools start hidden; the model must call ``load_connectors``
        before it can use them (progressive disclosure).

        Args:
            name: Unique connector name. Used as the tool-name prefix.
            description: Shown to the model when it lists available connectors.

        Returns:
            A `ConnectorBuilder` for registering tools under this connector.
        """
        self._connectors[name] = _ConnectorDefinition(
            name=name, description=description
        )
        return ConnectorBuilder(self, name)

    def enable_planner(self) -> Agent:
        """Enable the planning tool and suffix-based nag reminders.

        The planner escalates reminders at turns 4, 8, and 12 when no progress
        has been recorded. Call this before `run` or `session`.

        Returns:
            ``self``, for method chaining.
        """
        self._planner_enabled = True
        return self

    def enable_subagents(
        self, *, adapter_factory: Callable[[], ProviderAdapter]
    ) -> Agent:
        """Enable the subagent tool, using ``adapter_factory`` for spawned agents.

        Each spawned subagent gets a fresh adapter, fresh message history, and
        fresh cache. State crosses the boundary only through explicit
        ``input_handles``.

        Args:
            adapter_factory: Zero-argument callable that returns a fresh
                `ProviderAdapter` for each subagent.

        Returns:
            ``self``, for method chaining.
        """
        self._subagent_factory = adapter_factory
        return self

    def session(self) -> AgentSession:
        """Create a stateful `AgentSession` for multi-turn conversations.

        Returns:
            A new `AgentSession` backed by a copy of this agent's cache.
        """
        return AgentSession(self)

    def run_result(self, user_message: str) -> RunResult:
        """Run the agent and return the full `RunResult`.

        Builds a fresh `Harness` with a fresh message history for each call.

        Args:
            user_message: The user prompt to send.

        Returns:
            A `RunResult` with the text response, token usage, and cache state.
        """
        harness = self._make_harness()
        self._last_harness = harness
        result = harness.run_result(
            user_message, run_id=str(uuid.uuid4()), session_id=None
        )
        self._last_run_file = harness.run_file
        return result

    def run(self, user_message: str) -> str:
        """Run the agent and return the final text response.

        Args:
            user_message: The user prompt to send.

        Returns:
            The model's final text response.

        Raises:
            MaxTurnsExceeded: If the loop reaches ``max_turns``.
            RuntimeError: If the provider raises an exception.
        """
        harness = self._make_harness()
        self._last_harness = harness
        result = harness.run(user_message)
        self._last_run_file = harness.run_file
        return result

    def explain(self) -> str:
        """Return a string showing the equivalent explicit `Harness` wiring for this agent."""
        return _EXPLAIN_TEMPLATE.format(
            system=_truncate(self._system),
            max_turns=self._max_turns,
            run_dir=self._run_dir if self._run_dir is not None else "./runs",
        )

    def _build_tools(
        self,
        *,
        planner: Planner | None = None,
        cache: SessionCache | None = None,
    ) -> list[ToolSpec]:
        target_cache = cache if cache is not None else self._cache
        return _build_tools_for(self, planner=planner, cache=target_cache)

    def _make_harness(
        self,
        *,
        cache: SessionCache | None = None,
        planner: Planner | None = None,
    ) -> Harness:
        effective_cache = cache if cache is not None else self._cache
        effective_planner = (
            planner
            if planner is not None
            else Planner()
            if self._planner_enabled
            else None
        )
        tools = self._build_tools(planner=effective_planner, cache=effective_cache)
        if self._subagent_factory is not None:
            subagent_parent_tools = self._build_tools(
                planner=None, cache=effective_cache
            )
            effective_run_dir = (
                str(self._run_dir) if self._run_dir is not None else "./runs"
            )
            tools.append(
                make_subagent_spec(
                    adapter_factory=self._subagent_factory,
                    parent_tools=subagent_parent_tools,
                    parent_cache=effective_cache,
                    run_dir=effective_run_dir,
                    make_sub_tools=lambda sub_cache: self._build_tools(
                        planner=None, cache=sub_cache
                    ),
                )
            )
        harness_kwargs: dict = {
            "adapter": self._adapter,
            "system": self._system,
            "tools": tools,
            "max_turns": self._max_turns,
            "cache": effective_cache,
        }
        if self._run_dir is not None:
            harness_kwargs["run_dir"] = str(self._run_dir)

        harness = Harness(**harness_kwargs)
        if effective_planner is not None:
            harness.register_reminder(effective_planner.reminder_hook)
        return harness


class AgentSession:
    """Stateful chat session built from an `Agent` definition.

    `Agent.run()` intentionally stays one-shot for examples and tests. Use
    `Agent.session()` when an application needs follow-up questions over the
    same message history and cache handles.
    """

    def __init__(self, agent: Agent) -> None:
        self._agent = agent
        self._cache = SessionCache(
            sample_size=agent.cache.sample_size,
            storage_dir=None,
            hot_limit=agent.cache.hot_limit,
        )
        for name, value in agent.cache.items():
            self._cache.put(name, _copy_cache_value(value))
        self._harness = agent._make_harness(cache=self._cache)
        self._id: str = str(uuid.uuid4())
        self._last_result: RunResult | None = None
        self._turns: int = 0

    @property
    def id(self) -> str:
        return self._id

    @property
    def last_result(self) -> RunResult | None:
        return self._last_result

    @property
    def turns(self) -> int:
        return self._turns

    @property
    def cache(self) -> SessionCache:
        return self._cache

    @property
    def harness(self) -> Harness:
        return self._harness

    @property
    def run_file(self) -> str | None:
        return self._harness.run_file

    def put(self, name: str, value: Any, *, overwrite: bool = False) -> str:
        """Store a value in the session cache and return the handle used.

        Args:
            name: Desired handle name. Must be a valid Python identifier.
            value: Any Python object to store.
            overwrite: Replace the existing handle if ``True``.

        Returns:
            The handle name under which the value was stored.
        """
        return self._cache.put(name, value, overwrite=overwrite)

    def list_handles(self) -> dict[str, str]:
        """Return a mapping of all cache handle names to their snapshot strings."""
        return self._cache.list_handles()

    def ask_result(self, user_message: str) -> RunResult:
        """Send a follow-up message and return the full `RunResult`.

        Args:
            user_message: The follow-up user prompt.

        Returns:
            A `RunResult` for this turn sequence.
        """
        result = self._harness.ask_result(
            user_message, run_id=str(uuid.uuid4()), session_id=self._id
        )
        self._last_result = result
        self._turns += result.turns
        self._agent._last_harness = self._harness
        self._agent._last_run_file = self._harness.run_file
        return result

    def ask(self, user_message: str) -> str:
        """Send a follow-up message and return the final text response.

        Args:
            user_message: The follow-up user prompt.

        Returns:
            The model's final text response.

        Raises:
            MaxTurnsExceeded: If the loop reaches ``max_turns``.
            RuntimeError: If the provider raises an exception.
        """
        result = self.ask_result(user_message)
        if result.status == "max_turns_exceeded":
            from data_harness.exceptions import MaxTurnsExceeded

            raise MaxTurnsExceeded(result.turns)
        if result.status == "error":
            raise RuntimeError(result.error or "unknown error")
        return result.text


class AsyncAgent:
    """Async agent for use with `AsyncProviderAdapter`.

    `run()` and `run_result()` are coroutines. `run_stream()` is an async
    generator that yields text tokens as they arrive from the provider.
    Use `async_session()` for multi-turn streaming conversations.
    """

    def __init__(
        self,
        adapter: AsyncProviderAdapter,
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
        self._last_harness: AsyncHarness | None = None
        self._last_run_file: str | None = None
        self._connectors: dict[str, _ConnectorDefinition] = {}
        self._connector_tools: list[_ConnectorToolDefinition] = []
        self._planner_enabled = False

    @property
    def cache(self) -> SessionCache:
        return self._cache

    @property
    def last_harness(self) -> AsyncHarness | None:
        return self._last_harness

    @property
    def last_run_file(self) -> str | None:
        return self._last_run_file

    def connector(self, name: str, *, description: str) -> ConnectorBuilder:
        self._connectors[name] = _ConnectorDefinition(
            name=name, description=description
        )
        return ConnectorBuilder(self, name)

    def enable_planner(self) -> AsyncAgent:
        self._planner_enabled = True
        return self

    def async_session(self) -> AsyncAgentSession:
        return AsyncAgentSession(self)

    async def run_result(self, user_message: str) -> RunResult:
        harness = self._make_harness()
        self._last_harness = harness
        result = await harness.run_result(
            user_message, run_id=str(uuid.uuid4()), session_id=None
        )
        self._last_run_file = harness.run_file
        return result

    async def run(self, user_message: str) -> str:
        result = await self.run_result(user_message)
        from data_harness.exceptions import MaxTurnsExceeded

        if result.status == "max_turns_exceeded":
            raise MaxTurnsExceeded(result.turns)
        if result.status == "error":
            raise RuntimeError(result.error or "unknown error")
        return result.text

    async def run_stream(self, user_message: str) -> AsyncGenerator[StreamEvent, None]:
        """Stream events for a one-shot run.

        Yields StreamEvent objects (message_start, content_block_*, message_delta,
        message_stop, tool_result) following the Claude Agent SDK protocol.

        Usage::

            async for event in agent.run_stream("hello"):
                if event.type == "content_block_delta":
                    from data_harness.streaming import TextDelta
                    if isinstance(event.delta, TextDelta):
                        print(event.delta.text, end="", flush=True)
        """
        harness = self._make_harness()
        self._last_harness = harness
        async for event in harness.run_stream(user_message):
            yield event
        self._last_run_file = harness.run_file

    def _build_tools(
        self,
        *,
        planner: Planner | None = None,
        cache: SessionCache | None = None,
    ) -> list[ToolSpec]:
        target_cache = cache if cache is not None else self._cache
        return _build_tools_for(self, planner=planner, cache=target_cache)

    def _make_harness(
        self,
        *,
        cache: SessionCache | None = None,
        planner: Planner | None = None,
    ) -> AsyncHarness:
        effective_cache = cache if cache is not None else self._cache
        effective_planner = (
            planner
            if planner is not None
            else Planner()
            if self._planner_enabled
            else None
        )
        tools = self._build_tools(planner=effective_planner, cache=effective_cache)

        harness_kwargs: dict = {
            "adapter": self._adapter,
            "system": self._system,
            "tools": tools,
            "max_turns": self._max_turns,
            "cache": effective_cache,
        }
        if self._run_dir is not None:
            harness_kwargs["run_dir"] = str(self._run_dir)

        harness = AsyncHarness(**harness_kwargs)
        if effective_planner is not None:
            harness.register_reminder(effective_planner.reminder_hook)
        return harness


class AsyncAgentSession:
    """Stateful async chat session built from an `AsyncAgent` definition."""

    def __init__(self, agent: AsyncAgent) -> None:
        self._agent = agent
        self._cache = SessionCache(
            sample_size=agent.cache.sample_size,
            storage_dir=None,
            hot_limit=agent.cache.hot_limit,
        )
        for name, value in agent.cache.items():
            self._cache.put(name, _copy_cache_value(value))
        self._harness = agent._make_harness(cache=self._cache)
        self._id: str = str(uuid.uuid4())
        self._last_result: RunResult | None = None
        self._turns: int = 0

    @property
    def id(self) -> str:
        return self._id

    @property
    def last_result(self) -> RunResult | None:
        return self._last_result

    @property
    def turns(self) -> int:
        return self._turns

    @property
    def cache(self) -> SessionCache:
        return self._cache

    @property
    def harness(self) -> AsyncHarness:
        return self._harness

    @property
    def run_file(self) -> str | None:
        return self._harness.run_file

    def put(self, name: str, value: Any, *, overwrite: bool = False) -> str:
        return self._cache.put(name, value, overwrite=overwrite)

    def list_handles(self) -> dict[str, str]:
        return self._cache.list_handles()

    async def ask_result(self, user_message: str) -> RunResult:
        result = await self._harness.ask_result(
            user_message, run_id=str(uuid.uuid4()), session_id=self._id
        )
        self._last_result = result
        self._turns += result.turns
        self._agent._last_harness = self._harness
        self._agent._last_run_file = self._harness.run_file
        return result

    async def ask(self, user_message: str) -> str:
        result = await self.ask_result(user_message)
        if result.status == "max_turns_exceeded":
            from data_harness.exceptions import MaxTurnsExceeded

            raise MaxTurnsExceeded(result.turns)
        if result.status == "error":
            raise RuntimeError(result.error or "unknown error")
        return result.text

    async def ask_stream(self, user_message: str) -> AsyncGenerator[StreamEvent, None]:
        """Stream events for a follow-up turn."""
        async for event in self._harness.ask_stream(user_message):
            yield event
        self._agent._last_harness = self._harness
        self._agent._last_run_file = self._harness.run_file


_EXPLAIN_TEMPLATE = """\
Agent is a thin composition layer. The equivalent explicit wiring is:

    from data_harness.cache import SessionCache
    from data_harness.loop import Harness
    from data_harness.tools.interpreter import PythonInterpreter
    from data_harness.tools.variables import make_list_variables_spec

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
The message history resets per run; use agent.session().ask(...) for follow-up.
"""


def _truncate(text: str, limit: int = 80) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"
