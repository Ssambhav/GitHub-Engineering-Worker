"""Safe file writer tool."""

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Mapping

from tools.base import EngineeringTool
from tools.context import ToolContext, ToolRequest
from tools.implementations._filesystem import detect_encoding, resolve_workspace_path
from tools.metadata import ToolCapabilities, ToolMetadata
from tools.results import ToolArtifact, ToolResult


class FileWriterTool(EngineeringTool):
    metadata = ToolMetadata(
        identifier="file.writer",
        name="File Writer Tool",
        version="1.0.0",
        description="Write local files with backups, atomic replacement, and change detection.",
        capabilities=ToolCapabilities(("filesystem.write", "file.write")),
        side_effects=("write",),
        idempotency="conditionally_idempotent",
    )

    @classmethod
    def required_inputs(cls) -> tuple[str, ...]:
        return ("path", "content")

    def execute(self, request: ToolRequest, context: ToolContext, prepared: Mapping[str, Any]) -> ToolResult:
        path = resolve_workspace_path(context, str(request.inputs["path"]))
        content = str(request.inputs["content"])
        path.parent.mkdir(parents=True, exist_ok=True)
        existed = path.exists()
        encoding = detect_encoding(path, context.configuration.default_encoding) if existed else context.configuration.default_encoding
        old_content = path.read_text(encoding=encoding) if existed else None
        changed = old_content != content
        backup_path: Path | None = None
        if changed and existed:
            backup_dir = context.configuration.workspace_root / context.configuration.backup_directory_name
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_path = backup_dir / f"{path.name}.bak"
            backup_path.write_text(old_content or "", encoding=encoding)
        if changed:
            with NamedTemporaryFile("w", encoding=encoding, delete=False, dir=str(path.parent)) as handle:
                handle.write(content)
                temporary = Path(handle.name)
            temporary.replace(path)
        output = {
            "path": str(path),
            "encoding": encoding,
            "created": not existed,
            "changed": changed,
            "backup_path": str(backup_path) if backup_path else None,
            "bytes_written": len(content.encode(encoding)),
        }
        artifact = ToolArtifact("file-write", "file", str(path), {"changed": changed})
        return ToolResult.ok(metadata=self.metadata, structured_output=output, artifacts=(artifact,))
