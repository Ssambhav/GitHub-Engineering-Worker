"""Typed tool runtime configuration."""

from __future__ import annotations

from dataclasses import dataclass, replace
from os import environ
from pathlib import Path

from tools.exceptions import ToolConfigurationException


@dataclass(frozen=True, slots=True)
class ToolConfiguration:
    """Shared defaults and limits for local engineering tools."""

    workspace_root: Path
    max_file_size_bytes: int = 1_000_000
    max_search_results: int = 100
    max_traversal_depth: int = 25
    backup_directory_name: str = ".tool-backups"
    respect_gitignore: bool = True
    default_encoding: str = "utf-8"

    @classmethod
    def from_environment(cls, workspace_root: Path) -> "ToolConfiguration":
        config = cls(workspace_root=workspace_root)
        max_file_size = environ.get("GEW_TOOL_MAX_FILE_SIZE")
        max_results = environ.get("GEW_TOOL_MAX_SEARCH_RESULTS")
        max_depth = environ.get("GEW_TOOL_MAX_TRAVERSAL_DEPTH")
        if max_file_size:
            config = replace(config, max_file_size_bytes=int(max_file_size))
        if max_results:
            config = replace(config, max_search_results=int(max_results))
        if max_depth:
            config = replace(config, max_traversal_depth=int(max_depth))
        config.validate()
        return config

    def validate(self) -> None:
        if not self.workspace_root.exists() or not self.workspace_root.is_dir():
            raise ToolConfigurationException(f"workspace root is not a directory: {self.workspace_root}")
        if self.max_file_size_bytes <= 0:
            raise ToolConfigurationException("max_file_size_bytes must be positive")
        if self.max_search_results <= 0:
            raise ToolConfigurationException("max_search_results must be positive")
        if self.max_traversal_depth < 0:
            raise ToolConfigurationException("max_traversal_depth must be non-negative")
