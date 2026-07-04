"""Registry metadata models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from runtime.models.common import immutable_mapping


@dataclass(frozen=True, slots=True)
class RegistryMetadata:
    """Common registry metadata."""

    identifier: str
    name: str
    version: str
    description: str = ""
    capabilities: tuple[str, ...] = ()
    owner: str = "runtime"
    metadata: Mapping[str, Any] = field(default_factory=immutable_mapping)


@dataclass(frozen=True, slots=True)
class AgentMetadata(RegistryMetadata):
    """Registered agent metadata."""

    supported_stages: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ToolMetadata(RegistryMetadata):
    """Registered tool metadata."""

    side_effects: tuple[str, ...] = ()
    idempotency: str = "unknown"


@dataclass(frozen=True, slots=True)
class WorkflowMetadata(RegistryMetadata):
    """Registered workflow metadata."""

    initial_stage: str = "Receive Repository"
    terminal_stages: tuple[str, ...] = ("Completed", "Failed", "Cancelled")

