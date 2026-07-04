"""Notification fan-out service."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from notifications.models import Notification, NotificationResult, NotificationType


class NotificationProvider(Protocol):
    def send(self, notification: Notification) -> NotificationResult:
        """Send a notification."""


@dataclass(slots=True)
class NotificationService:
    """Optional notification layer that never blocks worker progress."""

    providers: tuple[NotificationProvider, ...] = ()
    enabled: bool = False
    enabled_types: set[NotificationType] = field(default_factory=lambda: set(NotificationType))

    def notify(self, notification: Notification) -> tuple[NotificationResult, ...]:
        if not self.enabled or notification.notification_type not in self.enabled_types:
            return (NotificationResult(False, "notification_service", "notifications disabled"),)
        results: list[NotificationResult] = []
        for provider in self.providers:
            try:
                results.append(provider.send(notification))
            except Exception as exc:
                results.append(NotificationResult(False, provider.__class__.__name__, str(exc)))
        return tuple(results)
