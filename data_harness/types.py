from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal


@dataclass(frozen=True)
class ToolAnnotations:
    title: str | None = None
    read_only: bool | None = None
    cache_mutating: bool | None = None
    destructive: bool | None = None
    open_world: bool | None = None


@dataclass
class TextBlock:
    text: str


@dataclass
class ToolUseBlock:
    tool_use_id: str
    tool_name: str
    tool_input: dict


@dataclass
class ToolResultBlock:
    tool_use_id: str
    content: str
    is_error: bool = False


ContentBlock = TextBlock | ToolUseBlock | ToolResultBlock


@dataclass
class Message:
    role: Literal["user", "assistant"]
    content: list[ContentBlock]

    def __post_init__(self) -> None:
        if self.role not in ("user", "assistant"):
            raise ValueError(
                f"Invalid role: {self.role!r}. Must be 'user' or 'assistant'."
            )


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict
    handler: Callable[..., Any] | None = None
    visible: bool = True
    annotations: ToolAnnotations | None = None

    def to_provider_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }
