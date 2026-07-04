"""Internal one-to-many event bus."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from threading import RLock
from uuid import uuid4

from runtime.exceptions import RuntimeException
from runtime.models.events import Event

EventHandler = Callable[[Event], None]


class InMemoryEventBus:
    """Thread-safe in-memory event bus.

    The bus is synchronous today but the API is intentionally small enough to
    support future async or durable implementations behind the same contract.
    """

    WILDCARD = "*"

    def __init__(self) -> None:
        self._lock = RLock()
        self._subscriptions: dict[str, tuple[str, EventHandler]] = {}
        self._by_event_type: dict[str, set[str]] = defaultdict(set)

    def subscribe(self, event_type: str, handler: EventHandler) -> str:
        if not event_type:
            raise RuntimeException("event_type is required")
        subscription_id = f"sub_{uuid4().hex}"
        with self._lock:
            self._subscriptions[subscription_id] = (event_type, handler)
            self._by_event_type[event_type].add(subscription_id)
        return subscription_id

    def unsubscribe(self, subscription_id: str) -> bool:
        with self._lock:
            record = self._subscriptions.pop(subscription_id, None)
            if record is None:
                return False
            event_type, _ = record
            self._by_event_type[event_type].discard(subscription_id)
            return True

    def publish(self, event: Event) -> None:
        handlers = self._handlers_for(event.event_type)
        for handler in handlers:
            handler(event)

    def _handlers_for(self, event_type: str) -> tuple[EventHandler, ...]:
        with self._lock:
            subscription_ids = set(self._by_event_type.get(event_type, set()))
            subscription_ids.update(self._by_event_type.get(self.WILDCARD, set()))
            return tuple(self._subscriptions[sub_id][1] for sub_id in subscription_ids if sub_id in self._subscriptions)

