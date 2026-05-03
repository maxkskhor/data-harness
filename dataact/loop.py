from __future__ import annotations

from typing import Callable

from dataact.cache import SessionCache
from dataact.exceptions import MaxTurnsExceeded, ToolNotFoundError
from dataact.format import format_tool_output
from dataact.logger import log_turn, setup_logger
from dataact.observe import time_block
from dataact.providers.base import NormalizedResponse, ProviderAdapter, StopReason
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
        self._adapter = adapter
        self._system = system
        self._tools = list(tools)
        self._max_turns = max_turns
        self._run_dir = run_dir
        self._cache = cache if cache is not None else SessionCache()
        self._messages: list[Message] = []
        self._reminders: list[Callable[[int, int], str | None]] = []

    def register_reminder(self, hook: Callable[[int, int], str | None]) -> None:
        self._reminders.append(hook)

    def run(self, user_message: str) -> str:
        run_file = setup_logger(self._run_dir)
        self._messages = [Message(role="user", content=[TextBlock(text=user_message)])]
        last_response: NormalizedResponse | None = None

        for turn in range(1, self._max_turns + 1):
            self._apply_reminders(turn)
            visible_tools = [t for t in self._tools if t.visible]

            with time_block() as tb:
                response = self._adapter.chat(
                    system=self._system,
                    messages=self._messages,
                    tools=visible_tools,
                )
            last_response = response
            latency = tb.elapsed_ms

            # Append assistant message
            self._messages.append(Message(role="assistant", content=response.content))

            tool_results: list[ToolResultBlock] = []

            if response.stop_reason == StopReason.TOOL_USE:
                tool_results = self._dispatch_tools(response.content)
                user_msg = Message(role="user", content=list(tool_results))
                self._messages.append(user_msg)

            log_turn(
                turn=turn,
                system=self._system,
                messages=self._messages,
                response=response,
                tool_results=tool_results,
                latency_ms=latency,
                run_file=run_file,
            )

            if response.stop_reason == StopReason.END_TURN:
                return self._extract_text(response)

            if turn == self._max_turns:
                raise MaxTurnsExceeded(turn, last_response)

        raise MaxTurnsExceeded(self._max_turns, last_response)

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
                results.append(ToolResultBlock(
                    tool_use_id=tub.tool_use_id,
                    content=f"Tool not found: {tub.tool_name!r}",
                    is_error=True,
                ))
                continue
            try:
                raw = spec.handler(**tub.tool_input)
                output = format_tool_output(raw, cache=self._cache)
            except Exception as exc:
                output = repr(exc)
                results.append(ToolResultBlock(
                    tool_use_id=tub.tool_use_id,
                    content=output,
                    is_error=True,
                ))
                continue
            results.append(ToolResultBlock(
                tool_use_id=tub.tool_use_id,
                content=output,
                is_error=False,
            ))

        return results

    def _extract_text(self, response: NormalizedResponse) -> str:
        texts = [b.text for b in response.content if isinstance(b, TextBlock)]
        return "\n".join(texts)
