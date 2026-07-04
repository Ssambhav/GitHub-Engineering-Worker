"""Strongly typed tool result objects."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any, Mapping

from runtime.models.common import immutable_mapping
from runtime.models.events import Event
from tools.metadata import ToolMetadata


class ToolStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class ToolArtifact:
    """Artifact produced by a tool."""

    artifact_id: str
    kind: str
    path: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=immutable_mapping)


@dataclass(frozen=True, slots=True)
class ToolResult:
    """Structured output returned by every tool."""

    status: ToolStatus
    metadata: ToolMetadata
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    artifacts: tuple[ToolArtifact, ...] = ()
    execution_time_ms: int = 0
    confidence_contribution: str = "neutral"
    events: tuple[Event, ...] = ()
    structured_output: Mapping[str, Any] = field(default_factory=immutable_mapping)

    @property
    def success(self) -> bool:
        return self.status == ToolStatus.SUCCESS

    @classmethod
    def ok(
        cls,
        *,
        metadata: ToolMetadata,
        structured_output: Mapping[str, Any] | None = None,
        artifacts: tuple[ToolArtifact, ...] = (),
        warnings: tuple[str, ...] = (),
        confidence_contribution: str = "increases",
    ) -> "ToolResult":
        return cls(
            status=ToolStatus.SUCCESS,
            metadata=metadata,
            structured_output=immutable_mapping(structured_output),
            artifacts=artifacts,
            warnings=warnings,
            confidence_contribution=confidence_contribution,
        )

    @classmethod
    def failure(
        cls,
        *,
        metadata: ToolMetadata,
        error: str,
        execution_time_ms: int,
        structured_output: Mapping[str, Any] | None = None,
    ) -> "ToolResult":
        return cls(
            status=ToolStatus.FAILED,
            metadata=metadata,
            errors=(error,),
            execution_time_ms=execution_time_ms,
            confidence_contribution="decreases",
            structured_output=immutable_mapping(structured_output),
        )

    def with_execution_time(self, execution_time_ms: int) -> "ToolResult":
        return replace(self, execution_time_ms=execution_time_ms)

    def with_events(self, events: tuple[Event, ...]) -> "ToolResult":
        return replace(self, events=(*self.events, *events))
