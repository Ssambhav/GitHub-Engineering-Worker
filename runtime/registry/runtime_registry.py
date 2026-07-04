"""Composite runtime registry."""

from __future__ import annotations

from dataclasses import dataclass, field

from runtime.models.registry import AgentMetadata, ToolMetadata, WorkflowMetadata
from runtime.registry.base import InMemoryRegistry


@dataclass(slots=True)
class RuntimeRegistry:
    """Container for agent, tool, and workflow registries."""

    agents: InMemoryRegistry[AgentMetadata] = field(default_factory=lambda: InMemoryRegistry("agent"))
    tools: InMemoryRegistry[ToolMetadata] = field(default_factory=lambda: InMemoryRegistry("tool"))
    workflows: InMemoryRegistry[WorkflowMetadata] = field(default_factory=lambda: InMemoryRegistry("workflow"))

