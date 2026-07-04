"""Agent task and result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping

from runtime.models.common import ArtifactRef, immutable_mapping, utc_now


@dataclass(frozen=True, slots=True)
class AgentTask:
    """A bounded request sent to an agent implementation."""

    task_id: str
    agent_id: str
    workflow_stage: str
    intent: str
    inputs: Mapping[str, Any] = field(default_factory=immutable_mapping)
    constraints: Mapping[str, Any] = field(default_factory=immutable_mapping)
    required_output: str | None = None
    created_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True, slots=True)
class AgentResult:
    """Structured result returned by an agent implementation."""

    task_id: str
    agent_id: str
    status: str
    summary: str
    artifact_refs: tuple[ArtifactRef, ...] = ()
    confidence: str = "unknown"
    next_recommended_action: str | None = None
    data: Mapping[str, Any] = field(default_factory=immutable_mapping)
    completed_at: datetime = field(default_factory=utc_now)

    @property
    def succeeded(self) -> bool:
        return self.status == "success"

