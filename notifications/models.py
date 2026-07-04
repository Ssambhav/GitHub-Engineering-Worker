"""Notification models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from runtime.models.common import immutable_mapping


class NotificationType(StrEnum):
    WORKER_STARTED = "worker_started"
    ISSUE_DETECTED = "issue_detected"
    ISSUE_SOLVED = "issue_solved"
    PULL_REQUEST_CREATED = "pull_request_created"
    RETRY_STARTED = "retry_started"
    RETRY_FAILED = "retry_failed"
    ESCALATION = "escalation"
    WORKER_ERROR = "worker_error"
    HEALTH_WARNING = "health_warning"


@dataclass(frozen=True, slots=True)
class Notification:
    notification_type: NotificationType
    title: str
    message: str
    repository: str | None = None
    issue: str | None = None
    severity: str = "info"
    fields: Mapping[str, Any] = field(default_factory=immutable_mapping)


@dataclass(frozen=True, slots=True)
class NotificationResult:
    sent: bool
    provider: str
    message: str
