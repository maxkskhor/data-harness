from __future__ import annotations

import dataclasses
from typing import Callable

from dataact.cache import SessionCache
from dataact.providers.base import ProviderAdapter
from dataact.types import ToolSpec

_SUBAGENT_TOOL_NAME = "subagent"

_WORKER_SYSTEM_TEMPLATE = """\
You are a clean-context worker invoked by another agent.

Your task: {task}

Available input handles (already loaded into your cache): {input_handles}

Use `python_interpreter` to inspect cached handles. Call `save(name, value)` for any
computed artifact worth returning. You must produce final text summarizing your
findings. If you save artifacts, mention what they contain and why they matter."""


def make_subagent_spec(
    adapter_factory: Callable[[], ProviderAdapter],
    parent_tools: list[ToolSpec],
    parent_cache: SessionCache,
    run_dir: str = "./runs",
    get_sub_cache: Callable[[], SessionCache] | None = None,
) -> ToolSpec:
    def subagent(
        task: str,
        input_handles: list[str] | None = None,
        output_policy: str = "text_only",
    ) -> str:
        from dataact.loop import Harness

        # Validate input_handles against parent cache
        if input_handles:
            missing = [h for h in input_handles if h not in parent_cache._store]
            if missing:
                return f"Error: input handles not found in parent cache: {missing}"

        # Build sub-cache
        if get_sub_cache is not None:
            sub_cache = get_sub_cache()
        else:
            sub_cache = SessionCache(sample_size=parent_cache.sample_size)

        # Copy requested handles into sub-cache
        if input_handles:
            for handle in input_handles:
                sub_cache.put(handle, parent_cache.get(handle))

        # Track pre-run handles to detect newly created ones
        pre_run_handles = set(sub_cache._store.keys())

        # Build sub-tools — exclude subagent to prevent recursion
        sub_tools = [
            dataclasses.replace(t)
            for t in parent_tools
            if t.name != _SUBAGENT_TOOL_NAME
        ]

        # Build system prompt
        handles_str = str(input_handles) if input_handles else "none"
        system = _WORKER_SYSTEM_TEMPLATE.format(task=task, input_handles=handles_str)

        # Spawn fresh adapter
        sub_adapter = adapter_factory()

        sub_harness = Harness(
            adapter=sub_adapter,
            system=system,
            tools=sub_tools,
            run_dir=run_dir,
            cache=sub_cache,
        )

        try:
            final_text = sub_harness.run(task)
        except Exception as exc:
            return f"Error: subagent failed: {type(exc).__name__}: {exc}"

        if output_policy == "text_only":
            return f"Subagent final output:\n{final_text}"

        # publish_created: find newly created handles
        new_handles = {
            name: val
            for name, val in sub_cache._store.items()
            if name not in pre_run_handles
        }

        if not new_handles:
            return f"Subagent final output:\n{final_text}\n\nPublished outputs: none"

        published_lines = []
        for sub_name, value in new_handles.items():
            parent_name = parent_cache.put(sub_name, value)
            snap = parent_cache.snapshot(parent_name)
            published_lines.append(f"- {sub_name} -> {parent_name}\n  Snapshot: {snap}")

        published_str = "\n".join(published_lines)
        return (
            f"Subagent final output:\n{final_text}\n\n"
            f"Published outputs:\n{published_str}"
        )

    return ToolSpec(
        name=_SUBAGENT_TOOL_NAME,
        description=(
            "Spawn a clean-context subagent to handle a subtask. "
            "The subagent has fresh message history and session cache. "
            "Use input_handles to pass data from this cache to the subagent."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Natural-language instruction for the subagent.",
                },
                "input_handles": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Parent cache handle names to copy into the subagent's cache."
                    ),
                },
                "output_policy": {
                    "type": "string",
                    "enum": ["text_only", "publish_created"],
                    "description": (
                        "'text_only': return only the subagent's final text. "
                        "'publish_created': also copy newly-created handles back to"
                        " parent cache."
                    ),
                },
            },
            "required": ["task"],
        },
        handler=subagent,
    )
