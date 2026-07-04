"""Runtime-facing service contracts for agents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from runtime.events import InMemoryEventBus
from runtime.interfaces import StructuredLogger
from runtime.registry import RuntimeRegistry


class MemoryAccess(Protocol):
    """Minimal memory interface available to agents."""

    def read(self, key: str) -> Mapping[str, Any] | None: ...

    def propose_update(self, key: str, value: Mapping[str, Any]) -> None: ...


class NullMemoryAccess:
    """Memory adapter used until a durable memory implementation is wired in."""

    def read(self, key: str) -> Mapping[str, Any] | None:
        return None

    def propose_update(self, key: str, value: Mapping[str, Any]) -> None:
        _ = (key, value)


class NullStructuredLogger:
    """Small logger implementation satisfying the runtime logging protocol."""

    def bind(self, **fields: object) -> "NullStructuredLogger":
        _ = fields
        return self

    def debug(self, message: str, **fields: object) -> None:
        _ = (message, fields)

    def info(self, message: str, **fields: object) -> None:
        _ = (message, fields)

    def warning(self, message: str, **fields: object) -> None:
        _ = (message, fields)

    def error(self, message: str, **fields: object) -> None:
        _ = (message, fields)


@dataclass(frozen=True, slots=True)
class RuntimeServices:
    """Services injected into an engineering agent."""

    registry: RuntimeRegistry | None = None
    event_bus: InMemoryEventBus | None = None
    memory: MemoryAccess = NullMemoryAccess()
    logger: StructuredLogger = NullStructuredLogger()
