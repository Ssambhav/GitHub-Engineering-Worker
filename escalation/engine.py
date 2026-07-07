"""Escalation rule evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from confidence.models import ConfidenceAssessment
from escalation.models import EscalationReport, EscalationRules


@dataclass(slots=True)
class EscalationEngine:
    """Turns unsafe or low-confidence evidence into escalation reports."""

    rules: EscalationRules = field(default_factory=EscalationRules)

    def evaluate(self, *, issue: str, repository: str, confidence: ConfidenceAssessment, evidence: dict[str, Any]) -> EscalationReport:
        reasons: list[str] = []
        retry_count = int(evidence.get("retry_count", 0))
        failure_count = int(evidence.get("failure_count", 0))
        failure_reason = str(evidence.get("failure_reason", "")).strip()
        if retry_count > self.rules.max_retries:
            reasons.append("maximum retries exceeded")
        if confidence.overall < self.rules.minimum_confidence:
            reasons.append("confidence below escalation threshold")
        if self.rules.escalate_on_unsafe_patch and evidence.get("unsafe_patch"):
            reasons.append("unsafe patch detected")
        if failure_count >= self.rules.repeated_failure_limit:
            reasons.append("repeated identical failures")
        if self.rules.escalate_on_repository_corruption and evidence.get("repository_corruption"):
            reasons.append("repository corruption detected")
        if self.rules.escalate_on_provider_unavailable and evidence.get("provider_unavailable"):
            reasons.append("AI provider unavailable")
        if failure_reason:
            reasons.append(failure_reason)
        elif evidence.get("unknown_failure"):
            reasons.append("unclassified failure requires investigation")
        return EscalationReport(
            should_escalate=bool(reasons),
            reasons=tuple(reasons),
            issue=issue,
            repository=repository,
            confidence=confidence.overall,
            retry_count=retry_count,
            recommended_action="human_review" if reasons else confidence.decision_recommendation,
        )
