"""Reusable abstract engineering agent implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from runtime.context import ExecutionContext
from runtime.models.agent import AgentResult, AgentTask
from runtime.models.events import Event, EventCategory
from runtime.models.registry import AgentMetadata

from agents.configuration import AgentConfiguration
from agents.contracts import RuntimeServices
from agents.exceptions import (
    AgentCancelledException,
    AgentConfigurationException,
    AgentExecutionException,
    AgentInitializationException,
    AgentValidationException,
)
from agents.models import EngineeringAgentMetadata
from agents.results import AgentResultBuilder


class EngineeringAgent(ABC):
    """Base class implementing the standard engineering agent lifecycle."""

    metadata: EngineeringAgentMetadata

    def __init__(
        self,
        *,
        configuration: AgentConfiguration | None = None,
        services: RuntimeServices | None = None,
    ) -> None:
        self.configuration = configuration or AgentConfiguration()
        self.services = services or RuntimeServices()
        self.configuration.validate()
        self.metadata.validate()
        self._initialized = False
        self._cancel_requested = False

    @property
    def agent_id(self) -> str:
        return self.metadata.identifier

    @property
    def version(self) -> str:
        return self.metadata.version

    @property
    def capabilities(self) -> tuple[str, ...]:
        return self.metadata.capabilities

    def runtime_metadata(self) -> AgentMetadata:
        return AgentMetadata(
            identifier=self.metadata.identifier,
            name=self.metadata.name,
            version=self.metadata.version,
            description=self.metadata.description,
            capabilities=self.metadata.capabilities,
            owner=self.metadata.owner,
            metadata=self.metadata.metadata,
            supported_stages=self.metadata.supported_stages,
        )

    def execute(self, task: AgentTask, context: ExecutionContext) -> AgentResult:
        builder = AgentResultBuilder(task)
        try:
            context.cancellation_token.throw_if_cancelled()
            self._raise_if_cancelled()
            self.initialize(context)
            self.validate(task, context)
            prepared = self.prepare(task, context, builder)
            output = self.perform(task, context, prepared, builder)
            confidence = self.confidence(task, context, output)
            self.finalize(task, context, output, builder)
            summary = self.summary(task, output)
            next_stage = self.next_stage(task, context, output)
            return builder.success(summary=summary, confidence=confidence, data=output, next_stage=next_stage)
        except AgentCancelledException:
            builder.errors.append("Agent execution was cancelled")
            return builder.failed(summary="Agent execution cancelled", confidence=0.0, data={"cancelled": True})
        except AgentValidationException as exc:
            builder.errors.append(str(exc))
            return builder.failed(summary=str(exc), confidence=0.0, data={"details": exc.details})
        except AgentExecutionException as exc:
            recovered = self.recover(task, context, exc, builder)
            if recovered is not None:
                return recovered
            builder.errors.append(str(exc))
            return builder.failed(summary=str(exc), confidence=0.0, data={"details": exc.details})
        finally:
            self.cleanup(context)

    def initialize(self, context: ExecutionContext) -> None:
        if not self.configuration.enabled:
            raise AgentConfigurationException(f"Agent is disabled: {self.agent_id}")
        try:
            self._initialized = True
            self._publish(context, "AgentInitialized", {"agent_id": self.agent_id})
        except Exception as exc:
            raise AgentInitializationException(f"Agent initialization failed: {self.agent_id}") from exc

    def validate(self, task: AgentTask, context: ExecutionContext) -> None:
        if task.agent_id != self.agent_id:
            raise AgentValidationException(
                "Task agent_id does not match agent identity",
                details={"task_agent_id": task.agent_id, "agent_id": self.agent_id},
            )
        if task.workflow_stage not in self.metadata.supported_stages:
            raise AgentValidationException(
                "Agent does not support task workflow stage",
                details={"stage": task.workflow_stage, "agent_id": self.agent_id},
            )
        if context.active_agent not in {None, self.agent_id}:
            raise AgentValidationException(
                "Execution context active agent does not match",
                details={"active_agent": context.active_agent, "agent_id": self.agent_id},
            )

    def prepare(self, task: AgentTask, context: ExecutionContext, builder: AgentResultBuilder) -> dict[str, Any]:
        _ = context
        builder.messages.append(f"Prepared {self.agent_id} for {task.workflow_stage}")
        return {"task_inputs": dict(task.inputs), "constraints": dict(task.constraints)}

    @abstractmethod
    def perform(
        self,
        task: AgentTask,
        context: ExecutionContext,
        prepared: dict[str, Any],
        builder: AgentResultBuilder,
    ) -> dict[str, Any]:
        """Run the agent-specific lifecycle body."""

    def finalize(
        self,
        task: AgentTask,
        context: ExecutionContext,
        output: dict[str, Any],
        builder: AgentResultBuilder,
    ) -> None:
        _ = task
        artifact = builder.artifact(
            f"{self.agent_id}.output",
            {"agent_id": self.agent_id, "stage": context.current_stage.value, "keys": tuple(sorted(output.keys()))},
        )
        builder.messages.append(f"Produced artifact {artifact.artifact_id}")
        self._publish(context, "AgentFinalized", {"agent_id": self.agent_id, "artifact_id": artifact.artifact_id})
        builder.events_published.append("AgentFinalized")

    def cleanup(self, context: ExecutionContext) -> None:
        if self._initialized:
            self._publish(context, "AgentCleanedUp", {"agent_id": self.agent_id})

    def cancel(self, reason: str | None = None) -> None:
        self._cancel_requested = True
        self.services.logger.warning("Agent cancellation requested", agent_id=self.agent_id, reason=reason)

    def recover(
        self,
        task: AgentTask,
        context: ExecutionContext,
        exc: AgentExecutionException,
        builder: AgentResultBuilder,
    ) -> AgentResult | None:
        _ = (task, context, exc, builder)
        return None

    def confidence(self, task: AgentTask, context: ExecutionContext, output: dict[str, Any]) -> float:
        _ = (task, context)
        warnings = len(tuple(output.get("missing_information", ()))) + len(tuple(output.get("warnings", ())))
        if warnings:
            return max(self.configuration.confidence_threshold, 0.75 - (warnings * 0.05))
        return 0.9

    def summary(self, task: AgentTask, output: dict[str, Any]) -> str:
        _ = output
        return f"{self.metadata.name} completed {task.workflow_stage}"

    def next_stage(self, task: AgentTask, context: ExecutionContext, output: dict[str, Any]) -> str | None:
        _ = (task, context, output)
        return None

    def _raise_if_cancelled(self) -> None:
        if self._cancel_requested:
            raise AgentCancelledException(f"Agent cancelled: {self.agent_id}")

    def _publish(self, context: ExecutionContext, event_type: str, payload: dict[str, Any]) -> None:
        if not self.configuration.publish_lifecycle_events or self.services.event_bus is None:
            return
        self.services.event_bus.publish(
            Event(
                event_type=event_type,
                category=EventCategory.AGENT,
                execution_id=context.execution_id,
                correlation_id=context.correlation_id,
                payload=payload,
                source=self.agent_id,
            )
        )
