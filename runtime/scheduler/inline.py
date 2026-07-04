"""Inline scheduler implementation."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


class InlineScheduler:
    """Deterministic scheduler that runs operations immediately."""

    def submit(self, operation: Callable[[], T]) -> T:
        return operation()

