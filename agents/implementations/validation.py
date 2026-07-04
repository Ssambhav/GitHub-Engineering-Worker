"""Validation agent."""

from __future__ import annotations

from typing import Any

from runtime.context import ExecutionContext
from runtime.models.agent import AgentTask
from runtime.models.workflow import WorkflowStage

from agents.base import EngineeringAgent
from agents.models import EngineeringAgentMetadata
from agents.results import AgentResultBuilder


class ValidationAgent(EngineeringAgent):
    """Validates artifact readiness and prepares validation requests."""

    metadata = EngineeringAgentMetadata(
        identifier="validation",
        name="Validation Agent",
        version="1.0.0",
        description="Validates workflow readiness without running test tools.",
        capabilities=("validation.readiness", "validation.summary", "validation.requests"),
        supported_stages=(WorkflowStage.VALIDATE.value, WorkflowStage.RUN_TESTS.value, WorkflowStage.DECISION_POINT.value),
    )

    def perform(
        self,
        task: AgentTask,
        context: ExecutionContext,
        prepared: dict[str, Any],
        builder: AgentResultBuilder,
    ) -> dict[str, Any]:
        _ = prepared
        artifact_count = len(context.temporary_artifacts)
        if task.workflow_stage == WorkflowStage.RUN_TESTS.value:
            builder.warnings.append("Test execution is deferred to a future tool-backed agent")
        return {
            "artifact_count": artifact_count,
            "workflow_readiness": {
                "has_issue": context.issue.issue_number > 0,
                "has_repository": bool(context.repository.full_name),
                "has_prior_artifacts": artifact_count > 0,
            },
            "validation_requests": self._validation_requests(task.workflow_stage),
            "validation_summary": f"Prepared validation metadata for {task.workflow_stage}",
            "missing_information": self._missing_information(task.workflow_stage),
            "stage": task.workflow_stage,
        }

    def summary(self, task: AgentTask, output: dict[str, Any]) -> str:
        return f"Generated validation summary for {task.workflow_stage} with {output['artifact_count']} prior artifacts"

    def _validation_requests(self, stage: str) -> tuple[str, ...]:
        if stage == WorkflowStage.RUN_TESTS.value:
            return ("future_test_execution_report",)
        if stage == WorkflowStage.DECISION_POINT.value:
            return ("validation_decision", "residual_risk_assessment")
        return ("diff_scope_review", "acceptance_mapping", "quality_gate_selection")

    def _missing_information(self, stage: str) -> tuple[str, ...]:
        if stage == WorkflowStage.RUN_TESTS.value:
            return ("test_commands", "test_execution_tool")
        return ()
