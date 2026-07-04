"""Common value objects used across the runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Event as ThreadingEvent
from types import MappingProxyType
from typing import Any, Mapping, NewType
from uuid import uuid4

ExecutionId = NewType("ExecutionId", str)
CorrelationId = NewType("CorrelationId", str)


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(UTC)


def new_execution_id(prefix: str = "exec") -> ExecutionId:
    """Create a stable execution id."""

    return ExecutionId(f"{prefix}_{uuid4().hex}")


def new_correlation_id(prefix: str = "corr") -> CorrelationId:
    """Create a stable correlation id."""

    return CorrelationId(f"{prefix}_{uuid4().hex}")


def immutable_mapping(values: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    """Return a read-only shallow copy of a mapping."""

    return MappingProxyType(dict(values or {}))


@dataclass(frozen=True, slots=True)
class RepositoryRef:
    """Repository identity and optional revision used by a workflow."""

    provider: str
    owner: str
    name: str
    default_branch: str = "main"
    revision: str | None = None

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"


@dataclass(frozen=True, slots=True)
class IssueRef:
    """Issue identity used by a workflow."""

    provider: str
    repository: str
    issue_number: int
    title: str | None = None
    url: str | None = None


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    """Reference to an artifact owned by another subsystem."""

    artifact_id: str
    kind: str
    uri: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=immutable_mapping)


@dataclass(frozen=True, slots=True)
class Confidence:
    """Confidence values reported by workflow phases."""

    issue_understanding: str = "unknown"
    repository_context: str = "unknown"
    root_cause: str = "unknown"
    plan: str = "unknown"
    patch: str = "unknown"
    validation: str = "unknown"
    overall: str = "unknown"


@dataclass(frozen=True, slots=True)
class TimelineEntry:
    """Single execution timeline entry."""

    timestamp: datetime
    stage: str
    event_type: str
    summary: str
    artifact_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RuntimeMetadata:
    """Execution metadata safe for internal logs and summaries."""

    created_at: datetime
    updated_at: datetime
    environment: str
    dry_run: bool
    labels: Mapping[str, str] = field(default_factory=immutable_mapping)


class CancellationToken:
    """Thread-safe cancellation token shared by runtime components."""

    def __init__(self) -> None:
        self._event = ThreadingEvent()
        self._reason: str | None = None

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    @property
    def reason(self) -> str | None:
        return self._reason

    def cancel(self, reason: str | None = None) -> None:
        self._reason = reason or "cancelled"
        self._event.set()

    def throw_if_cancelled(self) -> None:
        from runtime.exceptions import ExecutionCancelledException

        if self.is_cancelled:
            raise ExecutionCancelledException(self.reason or "Execution cancelled")

