"""Escalation models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from runtime.models.common import utc_now


@dataclass(frozen=True, slots=True)
class EscalationRules:
    """Configurable escalation triggers."""

    minimum_confidence: float = 40.0
    max_retries: int = 3
    repeated_failure_limit: int = 2
    escalate_on_unsafe_patch: bool = True
    escalate_on_repository_corruption: bool = True
    escalate_on_provider_unavailable: bool = True


@dataclass(frozen=True, slots=True)
class EscalationReport:
    """Structured escalation result."""

    should_escalate: bool
    reasons: tuple[str, ...]
    issue: str
    repository: str
    confidence: float
    retry_count: int
    recommended_action: str
    created_at: datetime = field(default_factory=utc_now)
