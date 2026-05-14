# Streaming

Stream event types yielded by `AsyncAgent.run_stream()` and
`AsyncAgentSession.ask_stream()`. The event protocol mirrors the Anthropic
SDK's raw SSE shape so callers get the same discriminated-union stream whether
they use `data-harness` or the SDK directly.

---

## StreamEvent

`StreamEvent` is a union alias for all event types:

```python
StreamEvent = (
    MessageStartEvent
    | ContentBlockStartEvent
    | ContentBlockDeltaEvent
    | ContentBlockStopEvent
    | MessageDeltaEvent
    | MessageStopEvent
    | ToolResultEvent
)
```

---

## Event types

::: data_harness.MessageStartEvent

::: data_harness.ContentBlockStartEvent

::: data_harness.ContentBlockDeltaEvent

::: data_harness.ContentBlockStopEvent

::: data_harness.MessageDeltaEvent

::: data_harness.MessageStopEvent

::: data_harness.ToolResultEvent

---

## Delta types

::: data_harness.TextDelta

::: data_harness.InputJSONDelta

---

## Iteration pattern

```python
async for event in agent.run_stream("Describe the dataset."):
    match event.type:
        case "content_block_delta":
            from data_harness import TextDelta
            if isinstance(event.delta, TextDelta):
                print(event.delta.text, end="", flush=True)
        case "tool_result":
            print(f"\n[{event.tool_name}] → {event.content[:80]}")
        case "message_stop":
            print()  # newline after final token
```
