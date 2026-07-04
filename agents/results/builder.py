"""Helpers for constructing runtime AgentResult objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any
from uuid import uuid4

from runtime.models.agent import AgentResult, AgentTask
from runtime.models.common import ArtifactRef, immutable_mapping


@dataclass(slots=True)
class AgentResultBuilder:
    """Collects structured result details during a lifecycle execution."""

    task: AgentTask
    started_at: float = field(default_factory=perf_counter)
    messages: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    artifacts: list[ArtifactRef] = field(default_factory=list)
    memory_updates: list[dict[str, Any]] = field(default_factory=list)
    events_published: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def artifact(self, kind: str, metadata: dict[str, Any]) -> ArtifactRef:
        ref = ArtifactRef(
            artifact_id=f"artifact_{uuid4().hex}",
            kind=kind,
            metadata=immutable_mapping(metadata),
        )
        self.artifacts.append(ref)
        return ref

    def success(self, *, summary: str, confidence: float, data: dict[str, Any], next_stage: str | None = None) -> AgentResult:
        return self._build("success", summary, confidence, data, next_stage)

    def failed(self, *, summary: str, confidence: float, data: dict[str, Any]) -> AgentResult:
        return self._build("failed", summary, confidence, data, None)

    def _build(
        self,
        status: str,
        summary: str,
        confidence: float,
        data: dict[str, Any],
        next_stage: str | None,
    ) -> AgentResult:
        duration_ms = int((perf_counter() - self.started_at) * 1000)
        payload = {
            "success": status == "success",
            "confidence_score": confidence,
            "messages": tuple(self.messages),
            "warnings": tuple(self.warnings),
            "errors": tuple(self.errors),
            "artifacts_produced": tuple(ref.artifact_id for ref in self.artifacts),
            "memory_updates": tuple(self.memory_updates),
            "events_published": tuple(self.events_published),
            "execution_duration_ms": duration_ms,
            "next_recommendations": tuple(self.recommendations),
            "metadata": dict(self.metadata),
            "output": data,
        }
        return AgentResult(
            task_id=self.task.task_id,
            agent_id=self.task.agent_id,
            status=status,
            summary=summary,
            artifact_refs=tuple(self.artifacts),
            confidence=f"{confidence:.2f}",
            next_recommended_action=next_stage,
            data=immutable_mapping(payload),
        )
