"""Safe file reader tool."""

from __future__ import annotations

from typing import Any, Mapping

from tools.base import EngineeringTool
from tools.context import ToolContext, ToolRequest
from tools.implementations._filesystem import detect_encoding, ensure_readable_file, resolve_workspace_path
from tools.metadata import ToolCapabilities, ToolMetadata
from tools.results import ToolArtifact, ToolResult


class FileReaderTool(EngineeringTool):
    metadata = ToolMetadata(
        identifier="file.reader",
        name="File Reader Tool",
        version="1.0.0",
        description="Read local text files safely with encoding detection and line ranges.",
        capabilities=ToolCapabilities(("filesystem.read", "file.read")),
    )

    @classmethod
    def required_inputs(cls) -> tuple[str, ...]:
        return ("path",)

    def execute(self, request: ToolRequest, context: ToolContext, prepared: Mapping[str, Any]) -> ToolResult:
        path = resolve_workspace_path(context, str(request.inputs["path"]))
        ensure_readable_file(path, context)
        encoding = detect_encoding(path, context.configuration.default_encoding)
        lines = path.read_text(encoding=encoding).splitlines()
        start = int(request.inputs.get("start_line", 1))
        end = int(request.inputs.get("end_line", len(lines)))
        bounded_start = max(start, 1)
        bounded_end = min(end, len(lines))
        selected = lines[bounded_start - 1 : bounded_end]
        output = {
            "path": str(path),
            "encoding": encoding,
            "line_count": len(lines),
            "start_line": bounded_start,
            "end_line": bounded_end,
            "content": "\n".join(selected),
        }
        artifact = ToolArtifact("file-read", "file_excerpt", str(path), {"line_count": len(selected)})
        return ToolResult.ok(metadata=self.metadata, structured_output=output, artifacts=(artifact,))
