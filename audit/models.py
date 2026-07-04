"""Audit log models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping
from uuid import uuid4

from runtime.models.common import immutable_mapping, utc_now


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """One structured audit event."""

    execution_id: str
    issue: str
    repository: str
    current_stage: str
    action: str
    result: str
    timestamp: datetime = field(default_factory=utc_now)
    audit_id: str = field(default_factory=lambda: f"audit_{uuid4().hex}")
    current_agent: str | None = None
    current_tool: str | None = None
    decision: str | None = None
    confidence: float | None = None
    retry_count: int = 0
    files_modified: tuple[str, ...] = ()
    tests_executed: tuple[str, ...] = ()
    execution_duration_ms: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=immutable_mapping)


@dataclass(frozen=True, slots=True)
class AuditQuery:
    """Simple query filters for JSONL audit logs."""

    execution_id: str | None = None
    issue: str | None = None
    repository: str | None = None
    action: str | None = None
