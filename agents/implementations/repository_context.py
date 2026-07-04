"""Repository context agent."""

from __future__ import annotations

from typing import Any

from runtime.context import ExecutionContext
from runtime.models.agent import AgentTask
from runtime.models.workflow import WorkflowStage

from agents.base import EngineeringAgent
from agents.exceptions import AgentValidationException
from agents.models import EngineeringAgentMetadata
from agents.results import AgentResultBuilder


class RepositoryContextAgent(EngineeringAgent):
    """Validates repository metadata and prepares repository context requests."""

    metadata = EngineeringAgentMetadata(
        identifier="repository_context",
        name="Repository Context Agent",
        version="1.0.0",
        description="Validates repository metadata and identifies required context without cloning or searching.",
        capabilities=("repository.validation", "repository.context", "repository.requirements"),
        supported_stages=(
            WorkflowStage.RECEIVE_REPOSITORY.value,
            WorkflowStage.COLLECT_CONTEXT.value,
            WorkflowStage.REPOSITORY_SEARCH.value,
            WorkflowStage.READ_RELEVANT_FILES.value,
        ),
    )

    def validate(self, task: AgentTask, context: ExecutionContext) -> None:
        super().validate(task, context)
        if not context.repository.owner or not context.repository.name:
            raise AgentValidationException("Repository owner and name are required")
        if not context.repository.provider:
            raise AgentValidationException("Repository provider is required")

    def perform(
        self,
        task: AgentTask,
        context: ExecutionContext,
        prepared: dict[str, Any],
        builder: AgentResultBuilder,
    ) -> dict[str, Any]:
        _ = prepared
        required_information = self._required_information(task.workflow_stage)
        repository = {
            "provider": context.repository.provider,
            "owner": context.repository.owner,
            "name": context.repository.name,
            "full_name": context.repository.full_name,
            "default_branch": context.repository.default_branch,
            "revision": context.repository.revision,
        }
        if task.workflow_stage in {
            WorkflowStage.REPOSITORY_SEARCH.value,
            WorkflowStage.READ_RELEVANT_FILES.value,
        }:
            builder.warnings.append("Repository search and file reads are deferred to future tool-backed agents")
        return {
            "repository_context": repository,
            "configuration_verified": bool(context.repository.default_branch),
            "required_information": tuple(required_information),
            "unsupported_actions": self._unsupported_actions(task.workflow_stage),
            "missing_information": (),
            "stage": task.workflow_stage,
        }

    def summary(self, task: AgentTask, output: dict[str, Any]) -> str:
        repository = output["repository_context"]["full_name"]
        return f"Prepared repository context for {repository} during {task.workflow_stage}"

    def _required_information(self, stage: str) -> tuple[str, ...]:
        if stage == WorkflowStage.REPOSITORY_SEARCH.value:
            return ("search_index_or_tool", "issue_terms", "candidate_paths")
        if stage == WorkflowStage.READ_RELEVANT_FILES.value:
            return ("file_paths", "line_ranges", "read_reason")
        return ("repository_manifest", "project_configuration", "contribution_guidance")

    def _unsupported_actions(self, stage: str) -> tuple[str, ...]:
        if stage == WorkflowStage.REPOSITORY_SEARCH.value:
            return ("repository_search",)
        if stage == WorkflowStage.READ_RELEVANT_FILES.value:
            return ("file_reading",)
        return ()
