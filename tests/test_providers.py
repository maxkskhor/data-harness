import copy
from unittest.mock import MagicMock, patch

from data_harness.providers.base import StopReason
from data_harness.types import Message, TextBlock, ToolSpec, ToolUseBlock


def make_anthropic_response(stop_reason="end_turn", content_blocks=None, usage=None):
    """Build a mock Anthropic SDK response object."""
    mock_resp = MagicMock()
    mock_resp.stop_reason = stop_reason
    mock_resp.content = content_blocks or []
    mock_resp.usage = MagicMock()
    if usage:
        mock_resp.usage.input_tokens = usage.get("input_tokens", 10)
        mock_resp.usage.output_tokens = usage.get("output_tokens", 5)
        mock_resp.usage.cache_read_input_tokens = usage.get("cache_read_tokens", 0)
        mock_resp.usage.cache_creation_input_tokens = usage.get("cache_write_tokens", 0)
    else:
        mock_resp.usage.input_tokens = 10
        mock_resp.usage.output_tokens = 5
        mock_resp.usage.cache_read_input_tokens = 0
        mock_resp.usage.cache_creation_input_tokens = 0
    return mock_resp


def make_sdk_text_block(text):
    b = MagicMock()
    b.type = "text"
    b.text = text
    return b


def make_sdk_tool_use_block(id_, name, input_):
    b = MagicMock()
    b.type = "tool_use"
    b.id = id_
    b.name = name
    b.input = input_
    return b


class TestStopReason:
    def test_values(self):
        assert StopReason.END_TURN.value == "end_turn"
        assert StopReason.TOOL_USE.value == "tool_use"
        assert StopReason.MAX_TOKENS.value == "max_tokens"
        assert StopReason.STOP_SEQUENCE.value == "stop_sequence"


class TestAnthropicAdapter:
    def _make_adapter(self):
        with patch("anthropic.Anthropic"):
            from data_harness.providers.anthropic import AnthropicAdapter

            adapter = AnthropicAdapter(model="claude-3-5-sonnet-20241022")
        return adapter

    def test_format_cache_control_returns_copy(self):
        adapter = self._make_adapter()
        original = {"type": "text", "text": "hello"}
        result = adapter.format_cache_control(original)
        assert result is not original
        assert result["cache_control"] == {"type": "ephemeral"}
        assert "cache_control" not in original

    def test_format_cache_control_has_all_original_fields(self):
        adapter = self._make_adapter()
        original = {"key": "value", "num": 42}
        result = adapter.format_cache_control(original)
        assert result["key"] == "value"
        assert result["num"] == 42

    def test_chat_end_turn(self):
        adapter = self._make_adapter()
        sdk_resp = make_anthropic_response(
            stop_reason="end_turn",
            content_blocks=[make_sdk_text_block("Hello!")],
            usage={
                "input_tokens": 10,
                "output_tokens": 5,
                "cache_read_tokens": 0,
                "cache_write_tokens": 0,
            },
        )
        adapter._client.messages.create.return_value = sdk_resp

        msgs = [Message(role="user", content=[TextBlock(text="Hi")])]
        tools = []
        resp = adapter.chat(system="sys", messages=msgs, tools=tools)

        assert resp.stop_reason == StopReason.END_TURN
        assert len(resp.content) == 1
        assert isinstance(resp.content[0], TextBlock)
        assert resp.content[0].text == "Hello!"
        assert resp.input_tokens == 10
        assert resp.output_tokens == 5

    def test_chat_tool_use(self):
        adapter = self._make_adapter()
        sdk_resp = make_anthropic_response(
            stop_reason="tool_use",
            content_blocks=[make_sdk_tool_use_block("tu_1", "my_tool", {"x": 1})],
        )
        adapter._client.messages.create.return_value = sdk_resp

        msgs = [Message(role="user", content=[TextBlock(text="run tool")])]
        resp = adapter.chat(system="sys", messages=msgs, tools=[])

        assert resp.stop_reason == StopReason.TOOL_USE
        assert isinstance(resp.content[0], ToolUseBlock)
        assert resp.content[0].tool_use_id == "tu_1"
        assert resp.content[0].tool_name == "my_tool"
        assert resp.content[0].tool_input == {"x": 1}

    def test_chat_max_tokens(self):
        adapter = self._make_adapter()
        sdk_resp = make_anthropic_response(stop_reason="max_tokens")
        adapter._client.messages.create.return_value = sdk_resp
        resp = adapter.chat(system="s", messages=[], tools=[])
        assert resp.stop_reason == StopReason.MAX_TOKENS

    def test_chat_stop_sequence(self):
        adapter = self._make_adapter()
        sdk_resp = make_anthropic_response(stop_reason="stop_sequence")
        adapter._client.messages.create.return_value = sdk_resp
        resp = adapter.chat(system="s", messages=[], tools=[])
        assert resp.stop_reason == StopReason.STOP_SEQUENCE

    def test_cache_read_write_tokens(self):
        adapter = self._make_adapter()
        sdk_resp = make_anthropic_response(
            usage={
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_read_tokens": 200,
                "cache_write_tokens": 300,
            },
        )
        adapter._client.messages.create.return_value = sdk_resp
        resp = adapter.chat(system="s", messages=[], tools=[])
        assert resp.cache_read_tokens == 200
        assert resp.cache_write_tokens == 300

    def test_adapter_input_immutability(self):
        adapter = self._make_adapter()
        sdk_resp = make_anthropic_response()
        adapter._client.messages.create.return_value = sdk_resp

        system = "The system prompt."
        messages = [
            Message(role="user", content=[TextBlock(text="hello")]),
            Message(role="assistant", content=[TextBlock(text="hi")]),
        ]
        tools = [
            ToolSpec(
                name="t", description="d", input_schema={"type": "object"}, handler=None
            )
        ]

        system_before = system
        messages_before = copy.deepcopy(messages)
        tools_before = copy.deepcopy(tools)

        adapter.chat(system=system, messages=messages, tools=tools)

        assert system == system_before
        assert len(messages) == len(messages_before)
        for m_orig, m_after in zip(messages_before, messages):
            assert m_orig.role == m_after.role
            assert len(m_orig.content) == len(m_after.content)
        assert len(tools) == len(tools_before)
        assert tools[0].name == tools_before[0].name

    def test_cache_control_only_in_adapter_payload(self):
        adapter = self._make_adapter()
        sdk_resp = make_anthropic_response()
        adapter._client.messages.create.return_value = sdk_resp

        messages = [
            Message(role="user", content=[TextBlock(text="hello")]),
            Message(role="assistant", content=[TextBlock(text="hi")]),
            Message(role="user", content=[TextBlock(text="again")]),
        ]
        tools = [ToolSpec(name="t", description="d", input_schema={}, handler=None)]

        adapter.chat(system="sys", messages=messages, tools=tools)

        call_kwargs = adapter._client.messages.create.call_args
        # The adapter call should have cache_control in system and last user message
        system_arg = call_kwargs.kwargs.get(
            "system", call_kwargs.args[0] if call_kwargs.args else None
        )
        # system might be a list with cache_control or a string
        if isinstance(system_arg, list):
            assert any("cache_control" in str(s) for s in system_arg)

        # Harness objects must not have cache_control
        for m in messages:
            for block in m.content:
                assert not hasattr(block, "cache_control")
