"""Strongly typed execution context."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Mapping

from runtime.models.common import (
    ArtifactRef,
    CancellationToken,
    Confidence,
    CorrelationId,
    ExecutionId,
    IssueRef,
    RepositoryRef,
    RuntimeMetadata,
    TimelineEntry,
    immutable_mapping,
    new_correlation_id,
    new_execution_id,
    utc_now,
)
from runtime.models.workflow import WorkflowStage, WorkflowState


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """Immutable workflow execution context.

    Mutable runtime concerns such as cancellation are referenced through a token,
    while context updates return a new instance. This makes orchestration steps
    explicit and auditable.
    """

    execution_id: ExecutionId
    correlation_id: CorrelationId
    issue: IssueRef
    repository: RepositoryRef
    current_stage: WorkflowStage
    current_state: WorkflowState
    metadata: RuntimeMetadata
    cancellation_token: CancellationToken
    active_agent: str | None = None
    memory_ref: str | None = None
    retry_count: int = 0
    confidence: Confidence = field(default_factory=Confidence)
    tool_outputs: Mapping[str, ArtifactRef] = field(default_factory=immutable_mapping)
    visited_states: tuple[WorkflowState, ...] = ()
    timeline: tuple[TimelineEntry, ...] = ()
    temporary_artifacts: tuple[ArtifactRef, ...] = ()
    data: Mapping[str, Any] = field(default_factory=immutable_mapping)

    def evolve(self, **changes: Any) -> "ExecutionContext":
        """Return a new context with selected fields changed."""

        if "metadata" not in changes:
            changes["metadata"] = replace(self.metadata, updated_at=utc_now())
        return replace(self, **changes)

    def with_stage(self, stage: WorkflowStage, state: WorkflowState | None = None) -> "ExecutionContext":
        """Move to a new stage and optionally a new workflow state."""

        next_state = state or self.current_state
        return self.evolve(
            current_stage=stage,
            current_state=next_state,
            visited_states=(*self.visited_states, next_state),
        )

    def with_active_agent(self, agent_id: str | None) -> "ExecutionContext":
        """Set the active agent for the current step."""

        return self.evolve(active_agent=agent_id)

    def with_retry_count(self, retry_count: int) -> "ExecutionContext":
        """Set the retry count."""

        return self.evolve(retry_count=retry_count)

    def add_timeline_entry(self, entry: TimelineEntry) -> "ExecutionContext":
        """Append a timeline entry."""

        return self.evolve(timeline=(*self.timeline, entry))

    def add_temporary_artifact(self, artifact: ArtifactRef) -> "ExecutionContext":
        """Append a temporary artifact reference."""

        return self.evolve(temporary_artifacts=(*self.temporary_artifacts, artifact))

    def record_tool_output(self, key: str, artifact: ArtifactRef) -> "ExecutionContext":
        """Record a tool output artifact reference."""

        outputs = dict(self.tool_outputs)
        outputs[key] = artifact
        return self.evolve(tool_outputs=immutable_mapping(outputs))

    def with_data(self, key: str, value: Any) -> "ExecutionContext":
        """Store bounded execution data."""

        data = dict(self.data)
        data[key] = value
        return self.evolve(data=immutable_mapping(data))


class ExecutionContextBuilder:
    """Factory for initial execution contexts."""

    def create(
        self,
        *,
        issue: IssueRef,
        repository: RepositoryRef,
        environment: str,
        dry_run: bool,
        labels: Mapping[str, str] | None = None,
        execution_id: ExecutionId | None = None,
        correlation_id: CorrelationId | None = None,
    ) -> ExecutionContext:
        metadata = RuntimeMetadata(
            created_at=utc_now(),
            updated_at=utc_now(),
            environment=environment,
            dry_run=dry_run,
            labels=immutable_mapping(labels or {}),
        )
        initial_state = WorkflowState.CREATED
        return ExecutionContext(
            execution_id=execution_id or new_execution_id(),
            correlation_id=correlation_id or new_correlation_id(),
            issue=issue,
            repository=repository,
            current_stage=WorkflowStage.RECEIVE_REPOSITORY,
            current_state=initial_state,
            metadata=metadata,
            cancellation_token=CancellationToken(),
            visited_states=(initial_state,),
        )

