"""Automatic discovery for built-in production tools."""

from __future__ import annotations

from typing import Type

from runtime.registry import RuntimeRegistry
from tools.base import EngineeringTool


def discover_tool_types() -> tuple[Type[EngineeringTool], ...]:
    from tools.implementations import (
        DiffGenerationTool,
        DirectoryTraversalTool,
        FileReaderTool,
        FileWriterTool,
        RepositoryMetadataTool,
        RepositorySearchTool,
    )

    return (
        RepositoryMetadataTool,
        RepositorySearchTool,
        FileReaderTool,
        FileWriterTool,
        DirectoryTraversalTool,
        DiffGenerationTool,
    )


def register_core_tools(runtime_registry: RuntimeRegistry) -> None:
    from tools.registry import ToolRegistry

    registry = ToolRegistry(runtime_registry)
    for tool_type in discover_tool_types():
        if not runtime_registry.tools.contains(tool_type.metadata.identifier):
            registry.register(tool_type)
