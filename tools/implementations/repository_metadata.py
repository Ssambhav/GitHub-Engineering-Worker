"""Repository metadata normalization tool."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from tools.base import EngineeringTool
from tools.context import ToolContext, ToolRequest
from tools.implementations._filesystem import resolve_workspace_path
from tools.metadata import ToolCapabilities, ToolMetadata
from tools.results import ToolArtifact, ToolResult


class RepositoryMetadataTool(EngineeringTool):
    metadata = ToolMetadata(
        identifier="repository.metadata",
        name="Repository Metadata Tool",
        version="1.0.0",
        description="Validate and normalize local repository metadata without cloning.",
        capabilities=ToolCapabilities(("repository.metadata", "repository.context")),
    )

    @classmethod
    def required_inputs(cls) -> tuple[str, ...]:
        return ("path",)

    def execute(self, request: ToolRequest, context: ToolContext, prepared: Mapping[str, Any]) -> ToolResult:
        root = resolve_workspace_path(context, str(request.inputs["path"]))
        manifests = [name for name in ("pyproject.toml", "package.json", "README.md", "AGENTS.md") if (root / name).exists()]
        output = {
            "root": str(root),
            "name": root.name,
            "exists": root.exists(),
            "is_directory": root.is_dir(),
            "has_git_directory": (root / ".git").exists(),
            "manifests": manifests,
            "default_branch": context.execution.repository.default_branch,
            "repository": context.execution.repository.full_name,
        }
        artifact = ToolArtifact("repository-metadata", "repository_metadata", str(root), {"manifest_count": len(manifests)})
        return ToolResult.ok(metadata=self.metadata, structured_output=output, artifacts=(artifact,))
