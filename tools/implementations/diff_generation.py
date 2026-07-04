"""Unified diff generation tool."""

from __future__ import annotations

from difflib import unified_diff
from typing import Any, Mapping

from tools.base import EngineeringTool
from tools.context import ToolContext, ToolRequest
from tools.implementations._filesystem import detect_encoding, ensure_readable_file, resolve_workspace_path
from tools.metadata import ToolCapabilities, ToolMetadata
from tools.results import ToolResult


class DiffGenerationTool(EngineeringTool):
    metadata = ToolMetadata(
        identifier="diff.generation",
        name="Diff Generation Tool",
        version="1.0.0",
        description="Compare local files or provided content and generate unified diffs.",
        capabilities=ToolCapabilities(("diff.generate", "filesystem.diff")),
    )

    def execute(self, request: ToolRequest, context: ToolContext, prepared: Mapping[str, Any]) -> ToolResult:
        left_name = str(request.inputs.get("left_name", "left"))
        right_name = str(request.inputs.get("right_name", "right"))
        if "left_path" in request.inputs:
            left_path = resolve_workspace_path(context, str(request.inputs["left_path"]))
            ensure_readable_file(left_path, context)
            left_text = left_path.read_text(encoding=detect_encoding(left_path, context.configuration.default_encoding))
            left_name = str(left_path)
        else:
            left_text = str(request.inputs.get("left_content", ""))
        if "right_path" in request.inputs:
            right_path = resolve_workspace_path(context, str(request.inputs["right_path"]))
            ensure_readable_file(right_path, context)
            right_text = right_path.read_text(encoding=detect_encoding(right_path, context.configuration.default_encoding))
            right_name = str(right_path)
        else:
            right_text = str(request.inputs.get("right_content", ""))
        diff_lines = list(
            unified_diff(
                left_text.splitlines(keepends=True),
                right_text.splitlines(keepends=True),
                fromfile=left_name,
                tofile=right_name,
            )
        )
        additions = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
        deletions = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))
        return ToolResult.ok(
            metadata=self.metadata,
            structured_output={
                "changed": left_text != right_text,
                "diff": "".join(diff_lines),
                "additions": additions,
                "deletions": deletions,
            },
        )
