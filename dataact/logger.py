from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

from dataact.providers.base import NormalizedResponse
from dataact.serialize import to_jsonable
from dataact.types import Message, ToolResultBlock


def setup_logger(run_dir: str = "./runs") -> str:
    """Create a timestamped JSONL file and configure loguru. Returns the path."""
    Path(run_dir).mkdir(parents=True, exist_ok=True)
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%S")
    run_file = str(Path(run_dir) / f"{ts}.jsonl")
    # Ensure the file exists
    Path(run_file).touch()
    logger.remove()
    logger.add(lambda msg: None, level="INFO")  # suppress default stderr; callers can add sinks
    return run_file


def log_turn(
    turn: int,
    system: str,
    messages: list[Message],
    response: NormalizedResponse,
    tool_results: list[ToolResultBlock],
    latency_ms: float,
    run_file: str,
) -> None:
    """Append one JSON line to the run JSONL file."""
    system_hash = hashlib.sha256(system.encode()).hexdigest()

    record: dict[str, Any] = {
        "turn": turn,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "system_hash": system_hash,
        "messages": to_jsonable(messages),
        "response_content": to_jsonable(response.content),
        "stop_reason": response.stop_reason.value,
        "tool_results": to_jsonable(tool_results),
        "metrics": {
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "cache_read_tokens": response.cache_read_tokens,
            "cache_write_tokens": response.cache_write_tokens,
            "latency_ms": latency_ms,
        },
    }

    if turn == 1:
        record["system"] = system

    with open(run_file, "a") as f:
        f.write(json.dumps(record) + "\n")
