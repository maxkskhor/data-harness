from __future__ import annotations

import asyncio
import dataclasses
import functools
from collections.abc import AsyncGenerator, Callable
from typing import Literal, cast

from data_harness.cache import SessionCache
from data_harness.exceptions import MaxTurnsExceeded
from data_harness.format import format_tool_output
from data_harness.logger import log_error_turn, log_turn, setup_logger
from data_harness.observe import time_block
from data_harness.providers.base import (
    AsyncProviderAdapter,
    NormalizedResponse,
    ProviderAdapter,
    StopReason,
)
from data_harness.result import CacheStorageInfo, RunResult, Usage
from data_harness.streaming import (
    StreamEvent,
    ToolResultEvent,
    accumulate_stream_events,
)
from data_harness.types import (
    Message,
    TextBlock,
    ToolResultBlock,
    ToolSpec,
    ToolUseBlock,
)

_MAX_TURN_REMINDER = (
    "This is the final turn. You MUST produce your complete final output now. "
    "Do not use any more tools. Respond with your answer directly."
)


class Harness:
    """The core synchronous ReAct loop.

    `Harness` owns the message list, dispatches tools, applies suffix-only
    reminder hooks, and logs every turn to a JSONL file. It is the central
    implementation boundary in data-harness: everything above it (`Agent`,
    `AgentSession`) is a convenience layer; everything below it
    (`ProviderAdapter`, `SessionCache`, `ToolSpec`) is a pure dependency.

    The system prompt is never mutated between turns. Reminders, nags, and
    dynamic state are always appended to the conversation suffix so the
    provider's KV cache is not invalidated.

    For most use cases, prefer `Agent` over constructing `Harness` directly.
    Use `Harness` when you need full control over tool wiring, as shown in
    ``examples/advanced_wiring.py``.

    Args:
        adapter: Synchronous provider adapter that translates provider SDK
            objects into harness types.
        system: System prompt. Kept byte-identical across all turns.
        tools: Full tool list. Invisible tools (``visible=False``) are excluded
            from the provider call but can still be dispatched.
        max_turns: Hard cap on provider turns before the loop stops and returns
            a ``"max_turns_exceeded"`` result.
        run_dir: Directory where JSONL logs are written. Created on first run.
        cache: Shared `SessionCache`. A fresh cache is created if ``None``.
    """

    def __init__(
        self,
        adapter: ProviderAdapter,
        system: str,
        tools: list[ToolSpec],
        max_turns: int = 25,
        run_dir: str = "./runs",
        cache: SessionCache | None = None,
    ) -> None:
        if max_turns < 1:
            raise ValueError(f"max_turns must be at least 1, got {max_turns!r}")
        self._adapter = adapter
        self._system = system
        self._tools = list(tools)
        self._max_turns = max_turns
        self._run_dir = run_dir
        self._cache = cache if cache is not None else SessionCache()
        self._messages: list[Message] = []
        self._reminders: list[Callable[[int, int], str | None]] = []
        self._run_file: str | None = None

    def register_reminder(self, hook: Callable[[int, int], str | None]) -> None:
        """Register a suffix reminder hook called before each provider turn.

        The hook receives ``(current_turn, max_turns)`` and returns a reminder
        string to append to the conversation suffix, or ``None`` to skip.

        Args:
            hook: Callable with signature ``(turn: int, max_turns: int) -> str | None``.
        """
        self._reminders.append(hook)

    def run_result(
        self,
        user_message: str,
        *,
        run_id: str | None = None,
        session_id: str | None = None,
    ) -> RunResult:
        """Start a fresh run and return the full `RunResult`.

        Resets message history. Use `ask_result` for follow-up turns on the
        same history.

        Args:
            user_message: The initial user prompt.
            run_id: Optional identifier stamped into the `RunResult`.
            session_id: Optional session identifier stamped into the `RunResult`.

        Returns:
            A `RunResult` describing the outcome, token usage, and cache state.
        """
        self._run_file = setup_logger(self._run_dir)
        self._messages = [Message(role="user", content=[TextBlock(text=user_message)])]
        result = self._run_loop_result()
        return dataclasses.replace(result, run_id=run_id, session_id=session_id)

    def ask_result(
        self,
        user_message: str,
        *,
        run_id: str | None = None,
        session_id: str | None = None,
    ) -> RunResult:
        """Append a follow-up message and continue the existing run.

        Appends ``user_message`` to the current history without resetting it.
        Useful for multi-turn sessions when driving `Harness` directly.

        Args:
            user_message: The follow-up user prompt.
            run_id: Optional identifier stamped into the `RunResult`.
            session_id: Optional session identifier stamped into the `RunResult`.

        Returns:
            A `RunResult` describing the outcome of this turn sequence.
        """
        if self._run_file is None:
            self._run_file = setup_logger(self._run_dir)
        self._messages.append(
            Message(role="user", content=[TextBlock(text=user_message)])
        )
        result = self._run_loop_result()
        return dataclasses.replace(result, run_id=run_id, session_id=session_id)

    def run(self, user_message: str) -> str:
        """Start a fresh run and return the final text response.

        Raises `MaxTurnsExceeded` if the loop hits ``max_turns``.

        Args:
            user_message: The initial user prompt.

        Returns:
            The model's final text response.

        Raises:
            MaxTurnsExceeded: If the loop reaches ``max_turns`` without stopping.
            RuntimeError: If the provider raises an exception during the run.
        """
        result = self.run_result(user_message)
        if result.status == "max_turns_exceeded":
            raise MaxTurnsExceeded(result.turns)
        if result.status == "error":
            raise RuntimeError(result.error or "unknown error")
        return result.text

    def ask(self, user_message: str) -> str:
        """Append a follow-up message and return the final text response.

        Args:
            user_message: The follow-up user prompt.

        Returns:
            The model's final text response.

        Raises:
            MaxTurnsExceeded: If the loop reaches ``max_turns`` without stopping.
            RuntimeError: If the provider raises an exception during the run.
        """
        result = self.ask_result(user_message)
        if result.status == "max_turns_exceeded":
            raise MaxTurnsExceeded(result.turns)
        if result.status == "error":
            raise RuntimeError(result.error or "unknown error")
        return result.text

    @property
    def run_file(self) -> str | None:
        """Path to the JSONL log for this run, or ``None`` before the first run."""
        return self._run_file

    def _run_loop_result(self) -> RunResult:
        if self._run_file is None:
            raise RuntimeError("run_file must be initialised before running the loop")

        total_usage = Usage()

        for turn in range(1, self._max_turns + 1):
            self._apply_reminders(turn)
            visible_tools = [t for t in self._tools if t.visible]

            try:
                with time_block() as tb:
                    response = self._adapter.chat(
                        system=self._system,
                        messages=self._messages,
                        tools=visible_tools,
                    )
            except Exception as exc:
                log_error_turn(
                    turn=turn,
                    system=self._system,
                    messages=self._messages,
                    error=repr(exc),
                    run_file=self._run_file,
                )
                return RunResult(
                    text="",
                    status="error",
                    turns=turn,
                    run_file=self._run_file,
                    stop_reason=None,
                    usage=total_usage,
                    cache_snapshots=self._cache.list_handles(),
                    cache_storage=self._build_cache_storage(),
                    error=repr(exc),
                )

            latency = tb.elapsed_ms

            total_usage = total_usage + Usage(
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cache_read_tokens=response.cache_read_tokens,
                cache_write_tokens=response.cache_write_tokens,
            )

            self._messages.append(Message(role="assistant", content=response.content))

            tool_results: list[ToolResultBlock] = []

            if response.stop_reason == StopReason.TOOL_USE:
                tool_results = self._dispatch_tools(response.content)
                user_msg = Message(role="user", content=list(tool_results))
                self._messages.append(user_msg)

            tool_error_count = sum(1 for r in tool_results if r.is_error)

            log_turn(
                turn=turn,
                system=self._system,
                messages=self._messages,
                response=response,
                tool_results=tool_results,
                latency_ms=latency,
                run_file=self._run_file,
                cache_storage=self._cache.storage_metadata(),
                visible_tools=[t.name for t in visible_tools],
                tool_error_count=tool_error_count,
                all_tools=self._tools,
            )

            if response.stop_reason != StopReason.TOOL_USE:
                return RunResult(
                    text=self._extract_text(response),
                    status="success",
                    turns=turn,
                    run_file=self._run_file,
                    stop_reason=response.stop_reason,
                    usage=total_usage,
                    cache_snapshots=self._cache.list_handles(),
                    cache_storage=self._build_cache_storage(),
                )

            if turn == self._max_turns:
                return RunResult(
                    text=self._extract_text(response),
                    status="max_turns_exceeded",
                    turns=turn,
                    run_file=self._run_file,
                    stop_reason=None,
                    usage=total_usage,
                    cache_snapshots=self._cache.list_handles(),
                    cache_storage=self._build_cache_storage(),
                )

    def _build_cache_storage(self) -> dict[str, CacheStorageInfo]:
        raw = self._cache.storage_metadata()
        return {
            name: CacheStorageInfo(
                location=cast(Literal["memory", "disk"], meta["location"]),
                storage_type=meta["storage_type"],
            )
            for name, meta in raw.items()
        }

    def _apply_reminders(self, turn: int) -> None:
        reminder_texts: list[str] = []

        for hook in self._reminders:
            text = hook(turn, self._max_turns)
            if text:
                reminder_texts.append(text)

        # Built-in max-turn reminder
        if turn == self._max_turns - 1:
            reminder_texts.append(_MAX_TURN_REMINDER)

        if not reminder_texts:
            return

        combined = "\n\n".join(reminder_texts)
        reminder_block = TextBlock(text=combined)

        # Append to existing user message or create a new one
        if self._messages and self._messages[-1].role == "user":
            self._messages[-1].content.append(reminder_block)
        else:
            self._messages.append(Message(role="user", content=[reminder_block]))

    def _dispatch_tools(self, content: list) -> list[ToolResultBlock]:
        tool_uses = [b for b in content if isinstance(b, ToolUseBlock)]
        results = []
        tool_map = {t.name: t for t in self._tools}

        for tub in tool_uses:
            spec = tool_map.get(tub.tool_name)
            if spec is None or spec.handler is None:
                results.append(
                    ToolResultBlock(
                        tool_use_id=tub.tool_use_id,
                        content=f"Tool not found: {tub.tool_name!r}",
                        is_error=True,
                    )
                )
                continue
            try:
                raw = spec.handler(**tub.tool_input)
                output = format_tool_output(raw, cache=self._cache)
            except Exception as exc:
                output = repr(exc)
                results.append(
                    ToolResultBlock(
                        tool_use_id=tub.tool_use_id,
                        content=output,
                        is_error=True,
                    )
                )
                continue
            results.append(
                ToolResultBlock(
                    tool_use_id=tub.tool_use_id,
                    content=output,
                    is_error=False,
                )
            )

        return results

    def _extract_text(self, response: NormalizedResponse) -> str:
        texts = [b.text for b in response.content if isinstance(b, TextBlock)]
        return "\n".join(texts)


class AsyncHarness:
    """Async variant of Harness. Requires an AsyncProviderAdapter.

    Exposes the same run_result / ask_result / run / ask surface as Harness,
    plus run_stream / ask_stream for token-level streaming.
    """

    def __init__(
        self,
        adapter: AsyncProviderAdapter,
        system: str,
        tools: list[ToolSpec],
        max_turns: int = 25,
        run_dir: str = "./runs",
        cache: SessionCache | None = None,
    ) -> None:
        if max_turns < 1:
            raise ValueError(f"max_turns must be at least 1, got {max_turns!r}")
        self._adapter = adapter
        self._system = system
        self._tools = list(tools)
        self._max_turns = max_turns
        self._run_dir = run_dir
        self._cache = cache if cache is not None else SessionCache()
        self._messages: list[Message] = []
        self._reminders: list[Callable[[int, int], str | None]] = []
        self._run_file: str | None = None

    def register_reminder(self, hook: Callable[[int, int], str | None]) -> None:
        self._reminders.append(hook)

    @property
    def run_file(self) -> str | None:
        return self._run_file

    async def run_result(
        self,
        user_message: str,
        *,
        run_id: str | None = None,
        session_id: str | None = None,
    ) -> RunResult:
        self._run_file = setup_logger(self._run_dir)
        self._messages = [Message(role="user", content=[TextBlock(text=user_message)])]
        result = await self._run_loop_result()
        return dataclasses.replace(result, run_id=run_id, session_id=session_id)

    async def ask_result(
        self,
        user_message: str,
        *,
        run_id: str | None = None,
        session_id: str | None = None,
    ) -> RunResult:
        if self._run_file is None:
            self._run_file = setup_logger(self._run_dir)
        self._messages.append(
            Message(role="user", content=[TextBlock(text=user_message)])
        )
        result = await self._run_loop_result()
        return dataclasses.replace(result, run_id=run_id, session_id=session_id)

    async def run(self, user_message: str) -> str:
        result = await self.run_result(user_message)
        if result.status == "max_turns_exceeded":
            raise MaxTurnsExceeded(result.turns)
        if result.status == "error":
            raise RuntimeError(result.error or "unknown error")
        return result.text

    async def ask(self, user_message: str) -> str:
        result = await self.ask_result(user_message)
        if result.status == "max_turns_exceeded":
            raise MaxTurnsExceeded(result.turns)
        if result.status == "error":
            raise RuntimeError(result.error or "unknown error")
        return result.text

    async def run_stream(self, user_message: str) -> AsyncGenerator[StreamEvent, None]:
        """Stream events for a one-shot run.

        Yields StreamEvent objects following the same protocol as the Claude
        Agent SDK.  Each provider turn emits message_start,
        content_block_start/delta/stop, message_delta, and message_stop events.
        After the harness dispatches a tool call a ToolResultEvent is emitted.
        The JSONL logger records fully assembled messages, not individual events.
        """
        self._run_file = setup_logger(self._run_dir)
        self._messages = [Message(role="user", content=[TextBlock(text=user_message)])]
        async for event in self._run_loop_stream():
            yield event

    async def ask_stream(self, user_message: str) -> AsyncGenerator[StreamEvent, None]:
        """Stream events for a follow-up turn in a session."""
        if self._run_file is None:
            self._run_file = setup_logger(self._run_dir)
        self._messages.append(
            Message(role="user", content=[TextBlock(text=user_message)])
        )
        async for event in self._run_loop_stream():
            yield event

    async def _run_loop_result(self) -> RunResult:
        if self._run_file is None:
            raise RuntimeError("run_file must be initialised before running the loop")

        total_usage = Usage()

        for turn in range(1, self._max_turns + 1):
            self._apply_reminders(turn)
            visible_tools = [t for t in self._tools if t.visible]

            try:
                with time_block() as tb:
                    response = await self._adapter.chat(
                        system=self._system,
                        messages=self._messages,
                        tools=visible_tools,
                    )
            except Exception as exc:
                log_error_turn(
                    turn=turn,
                    system=self._system,
                    messages=self._messages,
                    error=repr(exc),
                    run_file=self._run_file,
                )
                return RunResult(
                    text="",
                    status="error",
                    turns=turn,
                    run_file=self._run_file,
                    stop_reason=None,
                    usage=total_usage,
                    cache_snapshots=self._cache.list_handles(),
                    cache_storage=self._build_cache_storage(),
                    error=repr(exc),
                )

            latency = tb.elapsed_ms

            total_usage = total_usage + Usage(
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cache_read_tokens=response.cache_read_tokens,
                cache_write_tokens=response.cache_write_tokens,
            )

            self._messages.append(Message(role="assistant", content=response.content))

            tool_results: list[ToolResultBlock] = []

            if response.stop_reason == StopReason.TOOL_USE:
                tool_results = await self._dispatch_tools(response.content)
                self._messages.append(Message(role="user", content=list(tool_results)))

            tool_error_count = sum(1 for r in tool_results if r.is_error)

            log_turn(
                turn=turn,
                system=self._system,
                messages=self._messages,
                response=response,
                tool_results=tool_results,
                latency_ms=latency,
                run_file=self._run_file,
                cache_storage=self._cache.storage_metadata(),
                visible_tools=[t.name for t in visible_tools],
                tool_error_count=tool_error_count,
                all_tools=self._tools,
            )

            if response.stop_reason != StopReason.TOOL_USE:
                return RunResult(
                    text=self._extract_text(response),
                    status="success",
                    turns=turn,
                    run_file=self._run_file,
                    stop_reason=response.stop_reason,
                    usage=total_usage,
                    cache_snapshots=self._cache.list_handles(),
                    cache_storage=self._build_cache_storage(),
                )

            if turn == self._max_turns:
                return RunResult(
                    text=self._extract_text(response),
                    status="max_turns_exceeded",
                    turns=turn,
                    run_file=self._run_file,
                    stop_reason=None,
                    usage=total_usage,
                    cache_snapshots=self._cache.list_handles(),
                    cache_storage=self._build_cache_storage(),
                )

    async def _run_loop_stream(self) -> AsyncGenerator[StreamEvent, None]:
        if self._run_file is None:
            raise RuntimeError("run_file must be initialised before running the loop")

        total_usage = Usage()

        for turn in range(1, self._max_turns + 1):
            self._apply_reminders(turn)
            visible_tools = [t for t in self._tools if t.visible]

            events_this_turn: list[StreamEvent] = []

            with time_block() as tb:
                try:
                    async for evt in self._adapter.stream_events(
                        system=self._system,
                        messages=self._messages,
                        tools=visible_tools,
                    ):
                        events_this_turn.append(evt)
                        yield evt
                except Exception as exc:
                    log_error_turn(
                        turn=turn,
                        system=self._system,
                        messages=self._messages,
                        error=repr(exc),
                        run_file=self._run_file,
                    )
                    return

            latency = tb.elapsed_ms
            response = accumulate_stream_events(events_this_turn)

            total_usage = total_usage + Usage(
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cache_read_tokens=response.cache_read_tokens,
                cache_write_tokens=response.cache_write_tokens,
            )

            self._messages.append(Message(role="assistant", content=response.content))

            tool_results: list[ToolResultBlock] = []

            if response.stop_reason == StopReason.TOOL_USE:
                tool_results = await self._dispatch_tools(response.content)

                tool_name_map = {
                    b.tool_use_id: b.tool_name
                    for b in response.content
                    if isinstance(b, ToolUseBlock)
                }
                for result in tool_results:
                    yield ToolResultEvent(
                        tool_use_id=result.tool_use_id,
                        tool_name=tool_name_map.get(result.tool_use_id, ""),
                        content=result.content,
                        is_error=result.is_error,
                    )

                self._messages.append(Message(role="user", content=list(tool_results)))

            tool_error_count = sum(1 for r in tool_results if r.is_error)

            log_turn(
                turn=turn,
                system=self._system,
                messages=self._messages,
                response=response,
                tool_results=tool_results,
                latency_ms=latency,
                run_file=self._run_file,
                cache_storage=self._cache.storage_metadata(),
                visible_tools=[t.name for t in visible_tools],
                tool_error_count=tool_error_count,
                all_tools=self._tools,
            )

            if response.stop_reason != StopReason.TOOL_USE:
                return

            if turn == self._max_turns:
                return

    def _build_cache_storage(self) -> dict[str, CacheStorageInfo]:
        raw = self._cache.storage_metadata()
        return {
            name: CacheStorageInfo(
                location=cast(Literal["memory", "disk"], meta["location"]),
                storage_type=meta["storage_type"],
            )
            for name, meta in raw.items()
        }

    def _apply_reminders(self, turn: int) -> None:
        reminder_texts: list[str] = []

        for hook in self._reminders:
            text = hook(turn, self._max_turns)
            if text:
                reminder_texts.append(text)

        if turn == self._max_turns - 1:
            reminder_texts.append(_MAX_TURN_REMINDER)

        if not reminder_texts:
            return

        combined = "\n\n".join(reminder_texts)
        reminder_block = TextBlock(text=combined)

        if self._messages and self._messages[-1].role == "user":
            self._messages[-1].content.append(reminder_block)
        else:
            self._messages.append(Message(role="user", content=[reminder_block]))

    async def _dispatch_tools(self, content: list) -> list[ToolResultBlock]:
        tool_uses = [b for b in content if isinstance(b, ToolUseBlock)]
        results = []
        tool_map = {t.name: t for t in self._tools}

        for tub in tool_uses:
            spec = tool_map.get(tub.tool_name)
            if spec is None or spec.handler is None:
                results.append(
                    ToolResultBlock(
                        tool_use_id=tub.tool_use_id,
                        content=f"Tool not found: {tub.tool_name!r}",
                        is_error=True,
                    )
                )
                continue
            try:
                if asyncio.iscoroutinefunction(spec.handler):
                    raw = await spec.handler(**tub.tool_input)
                else:
                    raw = await asyncio.to_thread(
                        functools.partial(spec.handler, **tub.tool_input)
                    )
                output = format_tool_output(raw, cache=self._cache)
            except Exception as exc:
                output = repr(exc)
                results.append(
                    ToolResultBlock(
                        tool_use_id=tub.tool_use_id,
                        content=output,
                        is_error=True,
                    )
                )
                continue
            results.append(
                ToolResultBlock(
                    tool_use_id=tub.tool_use_id,
                    content=output,
                    is_error=False,
                )
            )

        return results

    def _extract_text(self, response: NormalizedResponse) -> str:
        texts = [b.text for b in response.content if isinstance(b, TextBlock)]
        return "\n".join(texts)
