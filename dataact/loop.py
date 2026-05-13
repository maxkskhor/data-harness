from __future__ import annotations

import dataclasses
from typing import Callable, Literal, cast

from dataact.cache import SessionCache
from dataact.exceptions import MaxTurnsExceeded
from dataact.format import format_tool_output
from dataact.logger import log_error_turn, log_turn, setup_logger
from dataact.observe import time_block
from dataact.providers.base import NormalizedResponse, ProviderAdapter, StopReason
from dataact.result import CacheStorageInfo, RunResult, Usage
from dataact.types import Message, TextBlock, ToolResultBlock, ToolSpec, ToolUseBlock

_MAX_TURN_REMINDER = (
    "This is the final turn. You MUST produce your complete final output now. "
    "Do not use any more tools. Respond with your answer directly."
)


class Harness:
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
        self._reminders.append(hook)

    def run_result(self, user_message: str, *,
                   run_id: str | None = None,
                   session_id: str | None = None) -> RunResult:
        self._run_file = setup_logger(self._run_dir)
        self._messages = [Message(role="user", content=[TextBlock(text=user_message)])]
        result = self._run_loop_result()
        return dataclasses.replace(result, run_id=run_id, session_id=session_id)

    def ask_result(self, user_message: str, *,
                   run_id: str | None = None,
                   session_id: str | None = None) -> RunResult:
        if self._run_file is None:
            self._run_file = setup_logger(self._run_dir)
        self._messages.append(
            Message(role="user", content=[TextBlock(text=user_message)])
        )
        result = self._run_loop_result()
        return dataclasses.replace(result, run_id=run_id, session_id=session_id)

    def run(self, user_message: str) -> str:
        result = self.run_result(user_message)
        if result.status == "max_turns_exceeded":
            raise MaxTurnsExceeded(result.turns)
        if result.status == "error":
            raise RuntimeError(result.error or "unknown error")
        return result.text

    def ask(self, user_message: str) -> str:
        result = self.ask_result(user_message)
        if result.status == "max_turns_exceeded":
            raise MaxTurnsExceeded(result.turns)
        if result.status == "error":
            raise RuntimeError(result.error or "unknown error")
        return result.text

    @property
    def run_file(self) -> str | None:
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
