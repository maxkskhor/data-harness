"""Typed result dataclasses for Harness and Agent run outputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from dataact.providers.base import StopReason


@dataclass
class Usage:
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
    location: Literal["memory", "disk"]
    storage_type: str

    def __post_init__(self) -> None:
        if self.location not in ("memory", "disk"):
            raise ValueError(f"Invalid location: {self.location!r}. Must be 'memory' or 'disk'.")


@dataclass
class RunResult:
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
