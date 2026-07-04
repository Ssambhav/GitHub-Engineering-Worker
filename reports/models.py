"""Strongly typed engineering reports."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from confidence.models import ConfidenceAssessment
from runtime.models.common import utc_now


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
    retries: int
    confidence: ConfidenceAssessment
    timeline: tuple[str, ...]
    final_decision: str
    next_recommendation: str
    created_at: datetime = field(default_factory=utc_now)
