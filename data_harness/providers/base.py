from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from data_harness.types import ContentBlock, Message, TextBlock, ToolSpec, ToolUseBlock

if TYPE_CHECKING:
    from data_harness.streaming import StreamEvent


class StopReason(Enum):
    END_TURN = "end_turn"
    TOOL_USE = "tool_use"
    MAX_TOKENS = "max_tokens"
    STOP_SEQUENCE = "stop_sequence"


@dataclass
class NormalizedResponse:
    stop_reason: StopReason
    content: list[ContentBlock]
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int


class ProviderAdapter(ABC):
    @abstractmethod
    def chat(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec],
    ) -> NormalizedResponse: ...

    @abstractmethod
    def format_cache_control(self, obj: dict) -> dict: ...


class AsyncProviderAdapter(ABC):
    @abstractmethod
    async def chat(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec],
    ) -> NormalizedResponse: ...

    @abstractmethod
    def format_cache_control(self, obj: dict) -> dict: ...

    async def stream_events(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec],
    ) -> AsyncGenerator[StreamEvent, None]:
        """Yield stream events for one provider turn.

        The default implementation calls chat() and synthesises the six
        standard event types from the assembled response.  Override in
        provider subclasses to emit real token-level events.
        """
        from data_harness.streaming import (
            ContentBlockDeltaEvent,
            ContentBlockStartEvent,
            ContentBlockStopEvent,
            InputJSONDelta,
            MessageDeltaEvent,
            MessageStartEvent,
            MessageStopEvent,
            TextDelta,
        )

        response = await self.chat(system, messages, tools)
        yield MessageStartEvent()
        for i, block in enumerate(response.content):
            if isinstance(block, TextBlock):
                yield ContentBlockStartEvent(index=i, content_block=TextBlock(text=""))
                yield ContentBlockDeltaEvent(index=i, delta=TextDelta(text=block.text))
                yield ContentBlockStopEvent(index=i)
            elif isinstance(block, ToolUseBlock):
                yield ContentBlockStartEvent(
                    index=i,
                    content_block=ToolUseBlock(
                        tool_use_id=block.tool_use_id,
                        tool_name=block.tool_name,
                        tool_input={},
                    ),
                )
                yield ContentBlockDeltaEvent(
                    index=i,
                    delta=InputJSONDelta(partial_json=json.dumps(block.tool_input)),
                )
                yield ContentBlockStopEvent(index=i)
        yield MessageDeltaEvent(
            stop_reason=response.stop_reason,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cache_read_tokens=response.cache_read_tokens,
            cache_write_tokens=response.cache_write_tokens,
        )
        yield MessageStopEvent()

    async def stream(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec],
        *,
        on_chunk: Callable[[str], Awaitable[None]],
    ) -> NormalizedResponse:
        """Backward-compat text-only streaming; calls stream_events() internally."""
        from data_harness.streaming import (
            ContentBlockDeltaEvent,
            TextDelta,
            accumulate_stream_events,
        )

        events = []
        async for evt in self.stream_events(system, messages, tools):
            events.append(evt)
            if isinstance(evt, ContentBlockDeltaEvent) and isinstance(
                evt.delta, TextDelta
            ):
                await on_chunk(evt.delta.text)
        return accumulate_stream_events(events)
