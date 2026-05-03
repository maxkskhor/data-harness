from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from dataact.types import ContentBlock, Message, ToolSpec


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
