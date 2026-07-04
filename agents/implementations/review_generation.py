"""Review generation agent."""

from __future__ import annotations

from typing import Any

from runtime.context import ExecutionContext
from runtime.models.agent import AgentTask
from runtime.models.workflow import WorkflowStage

from agents.base import EngineeringAgent
from agents.models import EngineeringAgentMetadata
from agents.results import AgentResultBuilder


class ReviewGenerationAgent(EngineeringAgent):
    """Builds a structured final engineering review object."""

    metadata = EngineeringAgentMetadata(
        identifier="review_generation",
        name="Review Generation Agent",
        version="1.0.0",
        description="Collects execution outputs and prepares a structured final report object.",
        capabilities=("review.structure", "review.summary", "review.report"),
        supported_stages=(WorkflowStage.REVIEW.value,),
    )

    def perform(
        self,
        task: AgentTask,
        context: ExecutionContext,
        prepared: dict[str, Any],
        builder: AgentResultBuilder,
    ) -> dict[str, Any]:
        _ = prepared
        artifact_ids = tuple(artifact.artifact_id for artifact in context.temporary_artifacts)
        report = {
            "execution_id": str(context.execution_id),
            "correlation_id": str(context.correlation_id),
            "issue": f"{context.issue.repository}#{context.issue.issue_number}",
            "repository": context.repository.full_name,
            "current_stage": context.current_stage.value,
            "artifact_refs": artifact_ids,
            "timeline_entries": len(context.timeline),
            "retry_count": context.retry_count,
        }
        return {
            "engineering_review": report,
            "execution_summary": {
                "status": "ready_for_terminal_summary",
                "artifacts_collected": len(artifact_ids),
                "markdown_generated": False,
            },
            "missing_information": (),
            "stage": task.workflow_stage,
        }

    def summary(self, task: AgentTask, output: dict[str, Any]) -> str:
        _ = task
        count = output["execution_summary"]["artifacts_collected"]
        return f"Prepared structured engineering review with {count} artifacts"
