"""Planning agent."""

from __future__ import annotations

from typing import Any

from runtime.context import ExecutionContext
from runtime.models.agent import AgentTask
from runtime.models.workflow import WorkflowStage

from agents.base import EngineeringAgent
from agents.models import EngineeringAgentMetadata
from agents.results import AgentResultBuilder


class PlanningAgent(EngineeringAgent):
    """Builds structured engineering plans and future execution requests."""

    metadata = EngineeringAgentMetadata(
        identifier="planning",
        name="Planning Agent",
        version="1.0.0",
        description="Constructs bounded engineering plans without patch generation or code modification.",
        capabilities=("planning.structure", "planning.prioritization", "planning.readiness"),
        supported_stages=(
            WorkflowStage.ANALYZE_ROOT_CAUSE.value,
            WorkflowStage.CREATE_ENGINEERING_PLAN.value,
            WorkflowStage.GENERATE_PATCH.value,
            WorkflowStage.APPLY_CHANGES.value,
        ),
    )

    def perform(
        self,
        task: AgentTask,
        context: ExecutionContext,
        prepared: dict[str, Any],
        builder: AgentResultBuilder,
    ) -> dict[str, Any]:
        _ = prepared
        plan = self._plan_for_stage(task.workflow_stage)
        if task.workflow_stage in {WorkflowStage.GENERATE_PATCH.value, WorkflowStage.APPLY_CHANGES.value}:
            builder.warnings.append("Patch generation and code modification are not implemented in this agent set")
        return {
            "analysis_inputs": tuple(sorted(context.data.keys())),
            "engineering_plan": plan,
            "prioritized_steps": tuple(step["id"] for step in plan),
            "readiness": {
                "has_issue_reference": context.issue.issue_number > 0,
                "has_repository_reference": bool(context.repository.full_name),
                "requires_future_capability": task.workflow_stage
                in {WorkflowStage.GENERATE_PATCH.value, WorkflowStage.APPLY_CHANGES.value},
            },
            "missing_information": self._missing_information(task.workflow_stage),
            "stage": task.workflow_stage,
        }

    def summary(self, task: AgentTask, output: dict[str, Any]) -> str:
        return f"Generated structured planning output with {len(output['engineering_plan'])} steps for {task.workflow_stage}"

    def _plan_for_stage(self, stage: str) -> tuple[dict[str, str], ...]:
        if stage == WorkflowStage.ANALYZE_ROOT_CAUSE.value:
            return (
                {"id": "collect_evidence", "description": "Collect confirmed issue and repository evidence."},
                {"id": "form_hypotheses", "description": "Record root-cause hypotheses for future analysis agents."},
                {"id": "identify_change_target", "description": "Identify the minimal target once evidence exists."},
            )
        if stage == WorkflowStage.GENERATE_PATCH.value:
            return ({"id": "request_patch_generation", "description": "Request a future patch generation agent."},)
        if stage == WorkflowStage.APPLY_CHANGES.value:
            return ({"id": "request_code_modification", "description": "Request a future code modification agent."},)
        return (
            {"id": "understand", "description": "Use normalized issue and repository context."},
            {"id": "design", "description": "Define bounded implementation and validation strategy."},
            {"id": "validate", "description": "Map expected evidence to acceptance criteria."},
        )

    def _missing_information(self, stage: str) -> tuple[str, ...]:
        if stage == WorkflowStage.ANALYZE_ROOT_CAUSE.value:
            return ("file_excerpts", "runtime_evidence")
        if stage == WorkflowStage.GENERATE_PATCH.value:
            return ("approved_patch_proposal",)
        if stage == WorkflowStage.APPLY_CHANGES.value:
            return ("approved_change_manifest",)
        return ()
