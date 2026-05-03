from __future__ import annotations

import copy

import anthropic

from dataact.providers.base import NormalizedResponse, ProviderAdapter, StopReason
from dataact.types import Message, TextBlock, ToolResultBlock, ToolSpec, ToolUseBlock

_STOP_REASON_MAP = {
    "end_turn": StopReason.END_TURN,
    "tool_use": StopReason.TOOL_USE,
    "max_tokens": StopReason.MAX_TOKENS,
    "stop_sequence": StopReason.STOP_SEQUENCE,
}


class AnthropicAdapter(ProviderAdapter):
    def __init__(self, model: str = "claude-sonnet-4-6", max_tokens: int = 8096) -> None:
        self._model = model
        self._max_tokens = max_tokens
        self._client = anthropic.Anthropic()

    def format_cache_control(self, obj: dict) -> dict:
        result = copy.copy(obj)
        result["cache_control"] = {"type": "ephemeral"}
        return result

    def chat(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec],
    ) -> NormalizedResponse:
        # Deep-copy inputs so we never mutate harness state
        api_system = self._build_system(system)
        api_messages = self._build_messages(messages)
        api_tools = self._build_tools(tools)

        resp = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=api_system,
            messages=api_messages,
            tools=api_tools or anthropic.NOT_GIVEN,
        )

        stop_reason = _STOP_REASON_MAP.get(resp.stop_reason, StopReason.END_TURN)
        content = self._normalize_content(resp.content)

        return NormalizedResponse(
            stop_reason=stop_reason,
            content=content,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
            cache_read_tokens=getattr(resp.usage, "cache_read_input_tokens", 0) or 0,
            cache_write_tokens=getattr(resp.usage, "cache_creation_input_tokens", 0) or 0,
        )

    def _build_system(self, system: str) -> list[dict]:
        return [self.format_cache_control({"type": "text", "text": system})]

    def _build_messages(self, messages: list[Message]) -> list[dict]:
        result = []
        for i, msg in enumerate(messages):
            blocks = [self._block_to_dict(b) for b in msg.content]
            # Apply cache_control to last user message
            if i == len(messages) - 1 and msg.role == "user" and blocks:
                last_block = blocks[-1]
                blocks[-1] = self.format_cache_control(last_block)
            result.append({"role": msg.role, "content": blocks})
        return result

    def _block_to_dict(self, block) -> dict:
        if isinstance(block, TextBlock):
            return {"type": "text", "text": block.text}
        if isinstance(block, ToolUseBlock):
            return {
                "type": "tool_use",
                "id": block.tool_use_id,
                "name": block.tool_name,
                "input": block.tool_input,
            }
        if isinstance(block, ToolResultBlock):
            return {
                "type": "tool_result",
                "tool_use_id": block.tool_use_id,
                "content": block.content,
                "is_error": block.is_error,
            }
        raise ValueError(f"Unknown block type: {type(block)}")

    def _build_tools(self, tools: list[ToolSpec]) -> list[dict]:
        return [t.to_provider_dict() for t in tools]

    def _normalize_content(self, content) -> list:
        blocks = []
        for block in content:
            if block.type == "text":
                blocks.append(TextBlock(text=block.text))
            elif block.type == "tool_use":
                blocks.append(ToolUseBlock(
                    tool_use_id=block.id,
                    tool_name=block.name,
                    tool_input=dict(block.input),
                ))
        return blocks
