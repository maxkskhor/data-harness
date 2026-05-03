from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dataact.providers.base import NormalizedResponse


class MaxTurnsExceeded(RuntimeError):
    def __init__(self, turns: int, last_response: "NormalizedResponse | None" = None):
        self.turns = turns
        self.last_response = last_response
        super().__init__(f"Max turns exceeded: {turns}")


class ToolNotFoundError(KeyError):
    pass


class SubagentRecursionError(RuntimeError):
    pass
