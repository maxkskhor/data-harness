# Types

Shared types used throughout the harness. All are exported from the top-level
`data_harness` package.

---

## ToolSpec

::: data_harness.ToolSpec

---

## Message

::: data_harness.Message

---

## TextBlock

::: data_harness.TextBlock

---

## ToolUseBlock

::: data_harness.ToolUseBlock

---

## ToolResultBlock

::: data_harness.ToolResultBlock

---

## ToolAnnotations

::: data_harness.ToolAnnotations

---

## ContentBlock

`ContentBlock` is a type alias for the union of the three block types that can
appear in a `Message`:

```python
ContentBlock = TextBlock | ToolUseBlock | ToolResultBlock
```
