from __future__ import annotations

import copy
import json

import openai

from dataact.providers.base import NormalizedResponse, ProviderAdapter, StopReason
from dataact.types import Message, TextBlock, ToolResultBlock, ToolSpec, ToolUseBlock

_STOP_REASON_MAP = {
    "stop": StopReason.END_TURN,
    "tool_calls": StopReason.TOOL_USE,
    "length": StopReason.MAX_TOKENS,
    # TODO: expose content-filter handling separately if the core stop model grows.
    "content_filter": StopReason.END_TURN,
    "function_call": StopReason.TOOL_USE,
}


class OpenAIAdapter(ProviderAdapter):
    def __init__(self, model: str = "gpt-4o-mini", max_tokens: int = 4096) -> None:
        self._model = model
        self._max_tokens = max_tokens
        self._client = openai.OpenAI()

    def format_cache_control(self, obj: dict) -> dict:
        return copy.copy(obj)

    def chat(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec],
    ) -> NormalizedResponse:
        api_messages = self._build_messages(system, messages)
        api_tools = self._build_tools(tools)

        response = self._client.chat.completions.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=api_messages,
            tools=api_tools or openai.NOT_GIVEN,
        )

        choice = response.choices[0]
        stop_reason = _STOP_REASON_MAP.get(choice.finish_reason, StopReason.END_TURN)

        return NormalizedResponse(
            stop_reason=stop_reason,
            content=self._normalize_message(choice.message),
            input_tokens=getattr(response.usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(response.usage, "completion_tokens", 0) or 0,
            cache_read_tokens=0,
            cache_write_tokens=0,
        )

    def _build_messages(self, system: str, messages: list[Message]) -> list[dict]:
        result = [{"role": "system", "content": system}]
        for message in messages:
            text_blocks = [b for b in message.content if isinstance(b, TextBlock)]
            tool_uses = [b for b in message.content if isinstance(b, ToolUseBlock)]
            tool_results = [
                b for b in message.content if isinstance(b, ToolResultBlock)
            ]

            for block in tool_results:
                result.append(
                    {
                        "role": "tool",
                        "tool_call_id": block.tool_use_id,
                        "content": block.content,
                    }
                )

            if text_blocks or tool_uses:
                api_message: dict = {
                    "role": message.role,
                    "content": "\n".join(b.text for b in text_blocks)
                    if text_blocks
                    else None,
                }
                if tool_uses:
                    api_message["tool_calls"] = [
                        {
                            "id": block.tool_use_id,
                            "type": "function",
                            "function": {
                                "name": block.tool_name,
                                "arguments": json.dumps(block.tool_input),
                            },
                        }
                        for block in tool_uses
                    ]
                result.append(api_message)
        return result

    def _build_tools(self, tools: list[ToolSpec]) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema,
                },
            }
            for tool in tools
        ]

    def _normalize_message(self, message) -> list:
        blocks = []
        content = getattr(message, "content", None)
        if content:
            blocks.append(TextBlock(text=content))

        for call in getattr(message, "tool_calls", None) or []:
            blocks.append(
                ToolUseBlock(
                    tool_use_id=call.id,
                    tool_name=call.function.name,
                    tool_input=json.loads(call.function.arguments or "{}"),
                )
            )
        return blocks
