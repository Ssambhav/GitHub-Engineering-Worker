"""Runtime event models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Mapping
from uuid import uuid4

from runtime.models.common import CorrelationId, ExecutionId, immutable_mapping, utc_now


class EventCategory(StrEnum):
    EXECUTION = "execution"
    LIFECYCLE = "lifecycle"
    STATE = "state"
    AGENT = "agent"
    TOOL = "tool"
    FAILURE = "failure"
    COMPLETION = "completion"


class EventSeverity(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class Event:
    """Typed internal runtime event."""

    event_type: str
    category: EventCategory
    execution_id: ExecutionId
    correlation_id: CorrelationId
    payload: Mapping[str, Any] = field(default_factory=immutable_mapping)
    severity: EventSeverity = EventSeverity.INFO
    event_id: str = field(default_factory=lambda: f"event_{uuid4().hex}")
    occurred_at: datetime = field(default_factory=utc_now)
    source: str = "runtime"

