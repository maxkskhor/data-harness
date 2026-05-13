from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum

from dataact.types import ContentBlock, Message, TextBlock, ToolSpec


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

    async def stream(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec],
        *,
        on_chunk: Callable[[str], Awaitable[None]],
    ) -> NormalizedResponse:
        """Default: full chat then deliver assembled text as one chunk.

        Override in provider-specific subclasses to enable real token streaming.
        """
        response = await self.chat(system, messages, tools)
        for block in response.content:
            if isinstance(block, TextBlock):
                await on_chunk(block.text)
        return response
