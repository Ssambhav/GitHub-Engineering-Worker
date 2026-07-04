"""Lifecycle and shutdown management."""

from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Callable
from threading import RLock

from runtime.events import InMemoryEventBus
from runtime.models.common import CorrelationId, ExecutionId, new_correlation_id, new_execution_id
from runtime.models.events import Event, EventCategory


@dataclass(slots=True)
class ShutdownManager:
    """Tracks shutdown state and notifies registered cleanup callbacks."""

    _callbacks: list[Callable[[], None]] = field(default_factory=list)
    _shutdown_requested: bool = False
    _reason: str | None = None

    @property
    def shutdown_requested(self) -> bool:
        return self._shutdown_requested

    @property
    def reason(self) -> str | None:
        return self._reason

    def register_cleanup(self, callback: Callable[[], None]) -> None:
        if self._shutdown_requested:
            callback()
            return
        self._callbacks.append(callback)

    def request_shutdown(self, reason: str | None = None) -> None:
        if self._shutdown_requested:
            return
        self._shutdown_requested = True
        self._reason = reason or "shutdown requested"
        callbacks = tuple(self._callbacks)
        self._callbacks.clear()
        for callback in callbacks:
            callback()


class LifecycleManager:
    """Owns runtime initialization and shutdown events."""

    def __init__(self, event_bus: InMemoryEventBus, shutdown_manager: ShutdownManager | None = None) -> None:
        self.event_bus = event_bus
        self.shutdown_manager = shutdown_manager or ShutdownManager()
        self._lock = RLock()
        self._initialized = False

    @property
    def initialized(self) -> bool:
        return self._initialized

    def initialize(self) -> None:
        with self._lock:
            if self._initialized:
                return
            self._initialized = True
        self.event_bus.publish(
            Event(
                event_type="RuntimeInitialized",
                category=EventCategory.LIFECYCLE,
                execution_id=new_execution_id("runtime"),
                correlation_id=new_correlation_id("runtime"),
                payload={"initialized": True},
                source="lifecycle",
            )
        )

    def shutdown(self, reason: str | None = None) -> None:
        self.shutdown_manager.request_shutdown(reason)
        self.event_bus.publish(
            Event(
                event_type="RuntimeShutdown",
                category=EventCategory.LIFECYCLE,
                execution_id=ExecutionId("runtime"),
                correlation_id=CorrelationId("runtime"),
                payload={"reason": self.shutdown_manager.reason},
                source="lifecycle",
            )
        )
