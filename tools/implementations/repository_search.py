"""Local repository search tool."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any, Mapping

from tools.base import EngineeringTool
from tools.context import ToolContext, ToolRequest
from tools.implementations._filesystem import detect_encoding, ensure_readable_file, iter_files, resolve_workspace_path
from tools.metadata import ToolCapabilities, ToolMetadata
from tools.results import ToolResult


@dataclass(frozen=True, slots=True)
class SearchMatch:
    path: str
    kind: str
    score: int
    line: int | None = None
    text: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"path": self.path, "kind": self.kind, "score": self.score, "line": self.line, "text": self.text}


class RepositorySearchTool(EngineeringTool):
    metadata = ToolMetadata(
        identifier="repository.search",
        name="Repository Search Tool",
        version="1.0.0",
        description="Search directories, filenames, symbols, and text in the local filesystem.",
        capabilities=ToolCapabilities(("repository.search", "filesystem.search", "symbol.search")),
    )

    @classmethod
    def required_inputs(cls) -> tuple[str, ...]:
        return ("path", "query")

    def execute(self, request: ToolRequest, context: ToolContext, prepared: Mapping[str, Any]) -> ToolResult:
        root = resolve_workspace_path(context, str(request.inputs["path"]))
        query = str(request.inputs["query"])
        modes = tuple(request.inputs.get("modes", ("filename", "text", "symbol", "directory")))
        max_results = int(request.inputs.get("max_results", context.configuration.max_search_results))
        matches: list[SearchMatch] = []
        query_lower = query.lower()
        for file_path in iter_files(root, context.configuration.max_traversal_depth):
            relative = str(file_path.relative_to(root))
            relative_lower = relative.lower()
            if "filename" in modes and query_lower in file_path.name.lower():
                matches.append(SearchMatch(relative, "filename", 90, text=file_path.name))
            if "directory" in modes and any(query_lower in part.lower() for part in file_path.parent.relative_to(root).parts):
                matches.append(SearchMatch(relative, "directory", 65, text=str(file_path.parent.relative_to(root))))
            if "text" in modes or "symbol" in modes:
                try:
                    ensure_readable_file(file_path, context)
                    text = file_path.read_text(encoding=detect_encoding(file_path, context.configuration.default_encoding))
                except Exception:
                    continue
                if "text" in modes:
                    for line_number, line in enumerate(text.splitlines(), start=1):
                        if query_lower in line.lower():
                            matches.append(SearchMatch(relative, "text", 80, line_number, line.strip()))
                if "symbol" in modes and file_path.suffix == ".py":
                    matches.extend(self._symbol_matches(root, file_path, text, query_lower))
        ranked = sorted(matches, key=lambda item: (-item.score, item.path, item.line or 0))[:max_results]
        return ToolResult.ok(
            metadata=self.metadata,
            structured_output={
                "root": str(root),
                "query": query,
                "match_count": len(ranked),
                "matches": [match.to_dict() for match in ranked],
            },
        )

    def _symbol_matches(self, root, file_path, text: str, query_lower: str) -> list[SearchMatch]:
        matches: list[SearchMatch] = []
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return matches
        relative = str(file_path.relative_to(root))
        for node in ast.walk(tree):
            name = getattr(node, "name", None)
            line = getattr(node, "lineno", None)
            if isinstance(name, str) and query_lower in name.lower():
                matches.append(SearchMatch(relative, "symbol", 100, line, name))
        return matches
