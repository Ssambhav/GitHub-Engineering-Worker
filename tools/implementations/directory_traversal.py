"""Directory traversal tool."""

from __future__ import annotations

from typing import Any, Mapping

from tools.base import EngineeringTool
from tools.context import ToolContext, ToolRequest
from tools.implementations._filesystem import iter_files, resolve_workspace_path
from tools.metadata import ToolCapabilities, ToolMetadata
from tools.results import ToolResult


class DirectoryTraversalTool(EngineeringTool):
    metadata = ToolMetadata(
        identifier="directory.traversal",
        name="Directory Traversal Tool",
        version="1.0.0",
        description="Traverse local directories with filtering, ignores, and depth limits.",
        capabilities=ToolCapabilities(("filesystem.traverse", "repository.tree")),
    )

    @classmethod
    def required_inputs(cls) -> tuple[str, ...]:
        return ("path",)

    def execute(self, request: ToolRequest, context: ToolContext, prepared: Mapping[str, Any]) -> ToolResult:
        root = resolve_workspace_path(context, str(request.inputs["path"]))
        max_depth = int(request.inputs.get("max_depth", context.configuration.max_traversal_depth))
        extensions = request.inputs.get("extensions")
        extension_filter = {str(item).lower() for item in extensions} if extensions else None
        files = sorted(str(path.relative_to(root)) for path in iter_files(root, max_depth, extension_filter))
        return ToolResult.ok(
            metadata=self.metadata,
            structured_output={"root": str(root), "file_count": len(files), "files": files},
        )
