"""Notification abstraction."""

from notifications.models import Notification, NotificationResult, NotificationType
from notifications.service import NotificationService

__all__ = ["Notification", "NotificationResult", "NotificationService", "NotificationType"]
