"""Issue understanding agent."""

from __future__ import annotations

from typing import Any

from runtime.context import ExecutionContext
from runtime.models.agent import AgentTask
from runtime.models.workflow import WorkflowStage

from agents.base import EngineeringAgent
from agents.exceptions import AgentValidationException
from agents.models import EngineeringAgentMetadata
from agents.results import AgentResultBuilder


class IssueUnderstandingAgent(EngineeringAgent):
    """Normalizes issue input and produces a structured issue brief."""

    metadata = EngineeringAgentMetadata(
        identifier="issue_understanding",
        name="Issue Understanding Agent",
        version="1.0.0",
        description="Validates and normalizes issue input without external GitHub calls.",
        capabilities=("issue.validation", "issue.normalization", "issue.summary"),
        supported_stages=(WorkflowStage.RECEIVE_ISSUE.value, WorkflowStage.UNDERSTAND_ISSUE.value),
    )

    def validate(self, task: AgentTask, context: ExecutionContext) -> None:
        super().validate(task, context)
        if context.issue.issue_number <= 0:
            raise AgentValidationException("Issue number must be positive")
        if not context.issue.repository:
            raise AgentValidationException("Issue repository is required")

    def perform(
        self,
        task: AgentTask,
        context: ExecutionContext,
        prepared: dict[str, Any],
        builder: AgentResultBuilder,
    ) -> dict[str, Any]:
        _ = prepared
        title = (context.issue.title or "").strip()
        missing = []
        if not title:
            missing.append("issue.title")
        if context.issue.url is None:
            missing.append("issue.url")
        summary = {
            "provider": context.issue.provider,
            "repository": context.issue.repository,
            "issue_number": context.issue.issue_number,
            "title": title,
            "url": context.issue.url,
            "normalized_key": f"{context.issue.repository}#{context.issue.issue_number}",
        }
        output = {
            "issue_summary": summary,
            "acceptance_criteria": (),
            "explicit_requirements": tuple(filter(None, (title,))),
            "assumptions": (),
            "missing_information": tuple(missing),
            "stage": task.workflow_stage,
        }
        builder.metadata["normalized_issue"] = summary["normalized_key"]
        if missing:
            builder.warnings.append("Issue input is missing optional descriptive fields")
        return output

    def summary(self, task: AgentTask, output: dict[str, Any]) -> str:
        issue = output["issue_summary"]["normalized_key"]
        return f"Normalized issue input for {issue} during {task.workflow_stage}"
