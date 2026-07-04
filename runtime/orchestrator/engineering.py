"""Engineering workflow orchestrator.

The orchestrator coordinates runtime components. It does not analyze
repositories, solve issues, generate patches, execute tools, or make product
decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from runtime.context import ExecutionContext
from runtime.dispatcher import RegisteredAgentDispatcher
from runtime.events import InMemoryEventBus
from runtime.exceptions import DispatchException, ExecutionCancelledException, WorkflowException
from runtime.models.agent import AgentResult, AgentTask
from runtime.models.common import ArtifactRef, TimelineEntry, utc_now
from runtime.models.events import Event, EventCategory, EventSeverity
from runtime.models.registry import AgentMetadata
from runtime.models.workflow import WorkflowStage, WorkflowState
from runtime.registry import RuntimeRegistry
from runtime.scheduler import InlineScheduler
from runtime.sessions import RuntimeSession, SessionManager


DEFAULT_STAGE_ORDER: tuple[WorkflowStage, ...] = (
    WorkflowStage.RECEIVE_REPOSITORY,
    WorkflowStage.RECEIVE_ISSUE,
    WorkflowStage.UNDERSTAND_ISSUE,
    WorkflowStage.COLLECT_CONTEXT,
    WorkflowStage.REPOSITORY_SEARCH,
    WorkflowStage.READ_RELEVANT_FILES,
    WorkflowStage.ANALYZE_ROOT_CAUSE,
    WorkflowStage.CREATE_ENGINEERING_PLAN,
    WorkflowStage.GENERATE_PATCH,
    WorkflowStage.APPLY_CHANGES,
    WorkflowStage.VALIDATE,
    WorkflowStage.RUN_TESTS,
    WorkflowStage.DECISION_POINT,
    WorkflowStage.REVIEW,
    WorkflowStage.COMPLETED,
)

TERMINAL_STAGES = {
    WorkflowStage.COMPLETED,
    WorkflowStage.FAILED,
    WorkflowStage.CANCELLED,
    WorkflowStage.ESCALATE,
}


@dataclass(frozen=True, slots=True)
class ExecutionSummary:
    """Final execution summary produced by the orchestrator."""

    execution_id: str
    correlation_id: str
    final_stage: str
    final_state: str
    visited_states: tuple[str, ...]
    timeline_entries: int
    retry_count: int
    artifact_refs: tuple[str, ...]
    status: str


class EngineeringOrchestrator:
    """Coordinates one workflow execution."""

    def __init__(
        self,
        *,
        registry: RuntimeRegistry,
        dispatcher: RegisteredAgentDispatcher,
        event_bus: InMemoryEventBus,
        session_manager: SessionManager,
        scheduler: InlineScheduler,
        max_steps: int = 128,
    ) -> None:
        self.registry = registry
        self.dispatcher = dispatcher
        self.event_bus = event_bus
        self.session_manager = session_manager
        self.scheduler = scheduler
        self.max_steps = max_steps

    def run(self, context: ExecutionContext) -> ExecutionSummary:
        """Run a workflow session until completion, escalation, failure, or cancellation."""

        session = self.session_manager.create_session(context)
        self._publish(context, "WorkflowStarted", EventCategory.EXECUTION, {"session_id": session.session_id})

        try:
            final_session = self.scheduler.submit(lambda: self._run_loop(session))
        except ExecutionCancelledException:
            cancelled = session.context.with_stage(WorkflowStage.CANCELLED, WorkflowState.CANCELLED)
            final_session = self.session_manager.update_context(session.session_id, cancelled)
            self._publish(cancelled, "WorkflowCancelled", EventCategory.COMPLETION, {}, EventSeverity.WARNING)
        except Exception as exc:
            failed = session.context.with_stage(WorkflowStage.FAILED, WorkflowState.FAILED)
            final_session = self.session_manager.update_context(session.session_id, failed)
            self._publish(
                failed,
                "WorkflowFailed",
                EventCategory.FAILURE,
                {"error": str(exc), "error_type": exc.__class__.__name__},
                EventSeverity.ERROR,
            )
            if isinstance(exc, WorkflowException):
                raise
        finally:
            self.session_manager.close(session.session_id)

        summary = self._summary(final_session.context)
        self._publish(final_session.context, "WorkflowSummaryGenerated", EventCategory.COMPLETION, {"summary": summary})
        return summary

    def _run_loop(self, session: RuntimeSession) -> RuntimeSession:
        current = session.context.with_stage(session.context.current_stage, WorkflowState.RUNNING)
        current = self._record_timeline(current, "Workflow running")
        session = self.session_manager.update_context(session.session_id, current)

        for _ in range(self.max_steps):
            context = session.context
            context.cancellation_token.throw_if_cancelled()

            if context.current_stage in TERMINAL_STAGES:
                terminal = self._finalize_terminal(context)
                return self.session_manager.update_context(session.session_id, terminal)

            agent_metadata = self._select_agent(context)
            task = self._build_task(context, agent_metadata)
            active = context.with_active_agent(agent_metadata.identifier)
            self._publish(active, "AgentDispatchStarted", EventCategory.AGENT, {"agent_id": agent_metadata.identifier})
            session = self.session_manager.update_context(session.session_id, active)

            try:
                result = self.dispatcher.dispatch(task, active)
            except DispatchException as exc:
                recovered = self._handle_failure(active, exc)
                return self.session_manager.update_context(session.session_id, recovered)

            updated = self._apply_agent_result(active, result)
            self._publish(
                updated,
                "AgentDispatchCompleted",
                EventCategory.AGENT,
                {"agent_id": result.agent_id, "status": result.status, "summary": result.summary},
            )
            session = self.session_manager.update_context(session.session_id, updated)

        raise WorkflowException("Workflow exceeded maximum orchestrator steps", details={"max_steps": self.max_steps})

    def _select_agent(self, context: ExecutionContext) -> AgentMetadata:
        candidates = [
            metadata
            for metadata in self.registry.agents.discover()
            if context.current_stage.value in metadata.supported_stages
        ]
        if not candidates:
            raise WorkflowException(
                f"No registered agent supports stage: {context.current_stage.value}",
                details={"stage": context.current_stage.value},
            )
        return sorted(candidates, key=lambda item: (item.name, item.version))[0]

    def _build_task(self, context: ExecutionContext, metadata: AgentMetadata) -> AgentTask:
        return AgentTask(
            task_id=f"task_{uuid4().hex}",
            agent_id=metadata.identifier,
            workflow_stage=context.current_stage.value,
            intent=f"Produce the required artifact for {context.current_stage.value}",
            inputs={
                "execution_id": str(context.execution_id),
                "correlation_id": str(context.correlation_id),
                "issue": context.issue,
                "repository": context.repository,
                "data": dict(context.data),
            },
            constraints={
                "no_business_logic_in_orchestrator": True,
                "dry_run": context.metadata.dry_run,
            },
            required_output="AgentResult",
        )

    def _apply_agent_result(self, context: ExecutionContext, result: AgentResult) -> ExecutionContext:
        if not result.succeeded:
            return self._handle_failure(context, WorkflowException(result.summary, details=dict(result.data)))

        next_stage = self._next_stage(context.current_stage, result)
        updated = context.with_active_agent(None).with_stage(next_stage, self._state_for_stage(next_stage))
        for artifact in result.artifact_refs:
            updated = updated.add_temporary_artifact(artifact)
        return self._record_timeline(updated, result.summary, tuple(ref.artifact_id for ref in result.artifact_refs))

    def _next_stage(self, current_stage: WorkflowStage, result: AgentResult) -> WorkflowStage:
        requested = result.next_recommended_action
        if requested:
            normalized = _stage_from_text(requested)
            if normalized is not None:
                return normalized
        try:
            index = DEFAULT_STAGE_ORDER.index(current_stage)
        except ValueError as exc:
            raise WorkflowException(f"Unknown workflow stage: {current_stage}") from exc
        if index + 1 >= len(DEFAULT_STAGE_ORDER):
            return WorkflowStage.COMPLETED
        return DEFAULT_STAGE_ORDER[index + 1]

    def _state_for_stage(self, stage: WorkflowStage) -> WorkflowState:
        if stage == WorkflowStage.RETRY:
            return WorkflowState.RETRYING
        if stage == WorkflowStage.ESCALATE:
            return WorkflowState.ESCALATING
        if stage == WorkflowStage.COMPLETED:
            return WorkflowState.COMPLETED
        if stage == WorkflowStage.FAILED:
            return WorkflowState.FAILED
        if stage == WorkflowStage.CANCELLED:
            return WorkflowState.CANCELLED
        return WorkflowState.RUNNING

    def _handle_failure(self, context: ExecutionContext, exc: Exception) -> ExecutionContext:
        self._publish(
            context,
            "FailureDetected",
            EventCategory.FAILURE,
            {"error": str(exc), "error_type": exc.__class__.__name__},
            EventSeverity.ERROR,
        )
        if context.retry_count <= 0:
            retry_context = context.with_retry_count(context.retry_count + 1).with_stage(
                WorkflowStage.RETRY,
                WorkflowState.RETRYING,
            )
            return self._record_timeline(retry_context, f"Failure routed to retry: {exc}")
        escalated = context.with_stage(WorkflowStage.ESCALATE, WorkflowState.ESCALATING)
        return self._record_timeline(escalated, f"Failure routed to escalation: {exc}")

    def _finalize_terminal(self, context: ExecutionContext) -> ExecutionContext:
        if context.current_stage == WorkflowStage.ESCALATE:
            self._publish(context, "WorkflowEscalated", EventCategory.COMPLETION, {}, EventSeverity.WARNING)
            return context
        if context.current_stage == WorkflowStage.CANCELLED:
            return context
        if context.current_stage == WorkflowStage.FAILED:
            return context
        completed = context.with_stage(WorkflowStage.COMPLETED, WorkflowState.COMPLETED)
        self._publish(completed, "WorkflowCompleted", EventCategory.COMPLETION, {})
        return self._record_timeline(completed, "Workflow completed")

    def _record_timeline(
        self,
        context: ExecutionContext,
        summary: str,
        artifact_refs: tuple[str, ...] = (),
    ) -> ExecutionContext:
        return context.add_timeline_entry(
            TimelineEntry(
                timestamp=utc_now(),
                stage=context.current_stage.value,
                event_type="orchestrator",
                summary=summary,
                artifact_refs=artifact_refs,
            )
        )

    def _publish(
        self,
        context: ExecutionContext,
        event_type: str,
        category: EventCategory,
        payload: object,
        severity: EventSeverity = EventSeverity.INFO,
    ) -> None:
        event_payload = payload if isinstance(payload, dict) else {"value": payload}
        self.event_bus.publish(
            Event(
                event_type=event_type,
                category=category,
                execution_id=context.execution_id,
                correlation_id=context.correlation_id,
                payload=event_payload,
                severity=severity,
                source="engineering_orchestrator",
            )
        )

    def _summary(self, context: ExecutionContext) -> ExecutionSummary:
        return ExecutionSummary(
            execution_id=str(context.execution_id),
            correlation_id=str(context.correlation_id),
            final_stage=context.current_stage.value,
            final_state=context.current_state.value,
            visited_states=tuple(state.value for state in context.visited_states),
            timeline_entries=len(context.timeline),
            retry_count=context.retry_count,
            artifact_refs=tuple(artifact.artifact_id for artifact in context.temporary_artifacts),
            status=context.current_state.value,
        )


def _stage_from_text(text: str) -> WorkflowStage | None:
    normalized = text.strip().lower().replace("_", " ")
    for stage in WorkflowStage:
        if stage.value.lower() == normalized or stage.name.lower().replace("_", " ") == normalized:
            return stage
    return None

