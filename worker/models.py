"""Worker runtime value objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from runtime.models.common import immutable_mapping, utc_now


@dataclass(frozen=True, slots=True)
class WorkerRepository:
    """Configured repository watched by the worker."""

    owner: str
    name: str
    default_branch: str = "main"

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"


@dataclass(frozen=True, slots=True)
class WorkerIssue:
    """Issue item persisted in the worker queue."""

    repository: str
    number: int
    title: str | None = None
    url: str | None = None
    labels: tuple[str, ...] = ()
    attempts: int = 0
    enqueued_at: datetime = field(default_factory=utc_now)
    metadata: Mapping[str, Any] = field(default_factory=immutable_mapping)

    @property
    def key(self) -> str:
        return f"{self.repository}#{self.number}"


@dataclass(frozen=True, slots=True)
class WorkerExecutionRecord:
    """Runtime tracking entry for a worker issue execution."""

    issue_key: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    summary: str | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class WorkerPaths:
    """Persistence paths used by the worker."""

    root: Path
    queue_file: Path
    processed_file: Path
    status_file: Path

    @classmethod
    def from_root(cls, root: Path) -> "WorkerPaths":
        worker_root = root / "worker"
        return cls(
            root=worker_root,
            queue_file=worker_root / "queue.json",
            processed_file=worker_root / "processed-issues.json",
            status_file=worker_root / "status.json",
        )
