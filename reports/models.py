"""Strongly typed engineering reports."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from confidence.models import ConfidenceAssessment
from runtime.models.common import utc_now


@dataclass(frozen=True, slots=True)
class StageTimelineEntry:
    """Detailed execution record for a single pipeline stage."""

    stage_name: str
    status: str
    start_time: datetime
    end_time: datetime
    exception: str | None
    exit_code: int | None
    stderr: str
    stdout: str
    returned_value: str


@dataclass(frozen=True, slots=True)
class EngineeringReport:
    """Maintainer-facing engineering report."""

    execution_id: str
    issue_summary: str
    repository: str
    root_cause: str
    files_read: tuple[str, ...]
    files_modified: tuple[str, ...]
    prompt_summary: str
    patch_summary: str
    validation: str
    tests: tuple[str, ...]
    verification_steps: tuple[str, ...]
    browser_actions: tuple[str, ...]
    screenshots: tuple[str, ...]
    why_fixed: str
    retries: int
    confidence: ConfidenceAssessment
    timeline: tuple[str, ...]
    execution_timeline: tuple[StageTimelineEntry, ...]
    final_decision: str
    next_recommendation: str
    created_at: datetime = field(default_factory=utc_now)
