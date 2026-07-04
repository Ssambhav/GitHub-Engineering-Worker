"""Strongly typed confidence models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping

from runtime.models.common import immutable_mapping, utc_now


@dataclass(frozen=True, slots=True)
class ConfidenceThresholds:
    """Configurable decision bands for autonomous work."""

    auto_pr: int = 90
    proceed: int = 75
    retry_allowed: int = 60
    additional_context: int = 40

    def recommendation_for(self, score: float) -> str:
        if score >= self.auto_pr:
            return "auto_pr"
        if score >= self.proceed:
            return "proceed"
        if score >= self.retry_allowed:
            return "retry_allowed"
        if score >= self.additional_context:
            return "additional_context"
        return "escalate"

    def band_for(self, score: float) -> str:
        if score >= self.auto_pr:
            return "very_high"
        if score >= self.proceed:
            return "high"
        if score >= self.retry_allowed:
            return "medium"
        if score >= self.additional_context:
            return "low"
        return "critical"


@dataclass(frozen=True, slots=True)
class StageConfidence:
    """Confidence score for one evidence stage."""

    stage: str
    score: float
    rationale: str
    weight: float = 1.0


@dataclass(frozen=True, slots=True)
class ConfidenceAssessment:
    """Confidence result with per-stage evidence and recommendation."""

    overall: float
    band: str
    per_stage: tuple[StageConfidence, ...]
    history: tuple[StageConfidence, ...]
    decision_recommendation: str
    calculated_at: datetime = field(default_factory=utc_now)
    metadata: Mapping[str, str] = field(default_factory=immutable_mapping)
