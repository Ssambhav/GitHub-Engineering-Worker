"""Reusable confidence engine for worker and workflow decisions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from confidence.models import ConfidenceAssessment, ConfidenceThresholds, StageConfidence


@dataclass(slots=True)
class ConfidenceEngine:
    """Calculates aggregate confidence from workflow evidence."""

    thresholds: ConfidenceThresholds = field(default_factory=ConfidenceThresholds)
    history: list[StageConfidence] = field(default_factory=list)

    def calculate(self, evidence: dict[str, Any]) -> ConfidenceAssessment:
        stages = (
            self._issue_understanding(evidence),
            self._repository_understanding(evidence),
            self._repository_search(evidence),
            self._context_quality(evidence),
            self._prompt_quality(evidence),
            self._ai_response(evidence),
            self._patch_quality(evidence),
            self._patch_validation(evidence),
            self._test_results(evidence),
            self._retry_count(evidence),
            self._failure_history(evidence),
        )
        self.history.extend(stages)
        weighted_total = sum(stage.score * stage.weight for stage in stages)
        weight = sum(stage.weight for stage in stages) or 1.0
        overall = round(max(0.0, min(100.0, weighted_total / weight)), 2)
        return ConfidenceAssessment(
            overall=overall,
            band=self.thresholds.band_for(overall),
            per_stage=stages,
            history=tuple(self.history),
            decision_recommendation=self.thresholds.recommendation_for(overall),
        )

    def _issue_understanding(self, evidence: dict[str, Any]) -> StageConfidence:
        issue = evidence.get("issue")
        score = 85.0 if issue and getattr(issue, "title", None) else 45.0
        if issue and getattr(issue, "url", None):
            score += 5.0
        return StageConfidence("issue_understanding", min(score, 100.0), "issue title and source metadata available", 1.1)

    def _repository_understanding(self, evidence: dict[str, Any]) -> StageConfidence:
        repo = evidence.get("repository")
        score = 85.0 if repo and getattr(repo, "full_name", None) else 50.0
        return StageConfidence("repository_understanding", score, "repository reference resolved", 1.0)

    def _repository_search(self, evidence: dict[str, Any]) -> StageConfidence:
        artifacts = int(evidence.get("artifact_count", 0))
        score = 65.0 + min(25.0, artifacts * 5.0)
        return StageConfidence("repository_search", score, "artifact count used as search/context proxy", 0.8)

    def _context_quality(self, evidence: dict[str, Any]) -> StageConfidence:
        timeline = int(evidence.get("timeline_entries", 0))
        score = 55.0 + min(35.0, timeline * 2.0)
        return StageConfidence("context_quality", score, "workflow timeline shows accumulated context", 1.1)

    def _prompt_quality(self, evidence: dict[str, Any]) -> StageConfidence:
        status = str(evidence.get("status", "unknown"))
        score = 80.0 if status in {"completed", "running"} else 55.0
        return StageConfidence("prompt_quality", score, "prompt quality inferred from workflow progression", 0.7)

    def _ai_response(self, evidence: dict[str, Any]) -> StageConfidence:
        final_stage = str(evidence.get("final_stage", ""))
        score = 85.0 if final_stage == "Completed" else 60.0
        return StageConfidence("ai_response", score, "AI response inferred from final workflow stage", 1.0)

    def _patch_quality(self, evidence: dict[str, Any]) -> StageConfidence:
        final_stage = str(evidence.get("final_stage", ""))
        score = 85.0 if final_stage in {"Completed", "Review"} else 55.0
        return StageConfidence("patch_quality", score, "patch quality inferred from downstream workflow stage", 1.2)

    def _patch_validation(self, evidence: dict[str, Any]) -> StageConfidence:
        status = str(evidence.get("status", ""))
        score = 90.0 if status == "completed" else 50.0
        return StageConfidence("patch_validation", score, "validation status from execution summary", 1.3)

    def _test_results(self, evidence: dict[str, Any]) -> StageConfidence:
        status = str(evidence.get("status", ""))
        score = 85.0 if status == "completed" else 50.0
        return StageConfidence("test_results", score, "test confidence inferred from terminal status", 1.2)

    def _retry_count(self, evidence: dict[str, Any]) -> StageConfidence:
        retries = int(evidence.get("retry_count", 0))
        score = max(20.0, 100.0 - retries * 18.0)
        return StageConfidence("retry_count", score, f"retry count: {retries}", 0.9)

    def _failure_history(self, evidence: dict[str, Any]) -> StageConfidence:
        failures = int(evidence.get("failure_count", 0))
        score = max(10.0, 95.0 - failures * 25.0)
        return StageConfidence("failure_history", score, f"failure count: {failures}", 1.0)
