"""Tool wrapper for the engineering execution pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from engineering import EngineeringExecutionPipeline
from engineering.configuration import EngineeringConfiguration
from engineering.models import EngineeringIssue
from tools.base import EngineeringTool
from tools.context import ToolContext, ToolRequest
from tools.metadata import ToolCapabilities, ToolMetadata
from tools.results import ToolResult


class EngineeringPipelineTool(EngineeringTool):
    metadata = ToolMetadata(
        identifier="engineering.pipeline",
        name="Engineering Pipeline Tool",
        version="1.0.0",
        description="Run repository search, context building, provider patch generation, validation, and dry-run application.",
        capabilities=ToolCapabilities(("engineering.pipeline", "engineering.solve", "patch.generate")),
        side_effects=("read", "write", "execute", "network"),
        idempotency="conditionally_idempotent",
    )

    @classmethod
    def required_inputs(cls) -> tuple[str, ...]:
        return ("repository_path", "repository", "issue_number", "issue_title")

    def execute(self, request: ToolRequest, context: ToolContext, prepared: Mapping[str, Any]) -> ToolResult:
        runtime_config = getattr(context.runtime_services, "configuration", None)
        config = EngineeringConfiguration(
            provider=str(request.inputs.get("provider", "auto")),
            model=request.inputs.get("model"),
            workspace_root=Path(str(getattr(getattr(runtime_config, "openclaw", None), "workspace", "."))),
            max_candidate_files=int(request.inputs.get("max_candidate_files", 12)),
            max_files_to_read=int(request.inputs.get("max_files_to_read", 6)),
            max_context_bytes=int(request.inputs.get("max_context_bytes", 80_000)),
        )
        issue = EngineeringIssue(
            repository=str(request.inputs["repository"]),
            number=int(request.inputs["issue_number"]),
            title=str(request.inputs["issue_title"]),
            body=request.inputs.get("issue_body"),
            labels=tuple(str(item) for item in request.inputs.get("labels", ())),
            url=request.inputs.get("issue_url"),
        )
        pipeline = EngineeringExecutionPipeline.create(config)
        result = pipeline.run_until_patch(
            repository_path=Path(str(request.inputs["repository_path"])),
            issue=issue,
            dry_run=bool(request.inputs.get("dry_run", context.execution.metadata.dry_run)),
            run_tests=bool(request.inputs.get("run_tests", False)),
        )
        return ToolResult.ok(
            metadata=self.metadata,
            structured_output={
                "issue": f"{result.issue.repository}#{result.issue.number}",
                "repository": result.repository,
                "patch_summary": result.patch_summary,
                "files_modified": list(result.files_modified),
                "tests_executed": [list(command.command) for command in result.tests_executed],
                "test_results": [
                    {"command": list(item.command), "exit_code": item.exit_code, "passed": item.passed}
                    for item in result.test_results
                ],
                "confidence": result.confidence,
                "warnings": list(result.warnings),
                "errors": list(result.errors),
                "engineering_notes": list(result.engineering_notes),
                "recommended_next_step": result.recommended_next_step,
            },
        )
