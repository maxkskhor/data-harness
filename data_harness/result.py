"""Typed result dataclasses for Harness and Agent run outputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from data_harness.providers.base import StopReason


@dataclass
class Usage:
    """Accumulated token counts for a run or session turn.

    Attributes:
        input_tokens: Tokens in the prompt sent to the provider.
        output_tokens: Tokens in the provider's response.
        cache_read_tokens: Prompt tokens served from the provider's KV cache.
        cache_write_tokens: Prompt tokens written to the provider's KV cache.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_read_tokens=self.cache_read_tokens + other.cache_read_tokens,
            cache_write_tokens=self.cache_write_tokens + other.cache_write_tokens,
        )


@dataclass
class CacheStorageInfo:
    """Where a named handle is physically stored in the `SessionCache`.

    Attributes:
        location: Either ``"memory"`` (hot) or ``"disk"`` (spilled cold).
        storage_type: Format used on disk, e.g. ``"dataframe_parquet"`` or
            ``"numpy_npy"``. Always ``"memory"`` for hot entries.
    """

    location: Literal["memory", "disk"]
    storage_type: str

    def __post_init__(self) -> None:
        if self.location not in ("memory", "disk"):
            raise ValueError(
                f"Invalid location: {self.location!r}. Must be 'memory' or 'disk'."
            )


@dataclass
class RunResult:
    """The complete outcome of a single `Harness.run()` or `Agent.run()` call.

    Attributes:
        text: The final text response from the model.
        status: ``"success"``, ``"max_turns_exceeded"``, or ``"error"``.
        turns: Number of provider turns executed.
        run_file: Path to the JSONL log for this run, or ``None`` if logging
            was disabled.
        stop_reason: Provider stop reason from the final turn, or ``None`` on
            error/max-turns.
        usage: Cumulative token counts across all turns.
        cache_snapshots: Mapping of handle name → compact snapshot string for
            every value in the session cache at the end of the run.
        cache_storage: Mapping of handle name → `CacheStorageInfo` describing
            where each handle is stored.
        error: Exception repr when ``status == "error"``, otherwise ``None``.
        run_id: Optional UUID assigned by `Agent`; ``None`` when using `Harness`
            directly.
        session_id: Optional session UUID when the run is part of an
            `AgentSession`; ``None`` for one-shot runs.
    """

    text: str
    status: Literal["success", "max_turns_exceeded", "error"]
    turns: int
    run_file: str | None
    stop_reason: StopReason | None
    usage: Usage
    cache_snapshots: dict[str, str] = field(default_factory=dict)
    cache_storage: dict[str, CacheStorageInfo] = field(default_factory=dict)
    error: str | None = None
    run_id: str | None = None
    session_id: str | None = None
