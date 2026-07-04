"""Agent metadata models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from runtime.models.common import immutable_mapping


@dataclass(frozen=True, slots=True)
class EngineeringAgentMetadata:
    """Metadata owned by an EngineeringAgent implementation."""

    identifier: str
    name: str
    version: str
    description: str
    capabilities: tuple[str, ...]
    supported_stages: tuple[str, ...]
    owner: str = "agents"
    metadata: Mapping[str, Any] = field(default_factory=immutable_mapping)

    def validate(self) -> None:
        if not self.identifier:
            raise ValueError("agent identifier is required")
        if not self.name:
            raise ValueError("agent name is required")
        if not self.version or "." not in self.version:
            raise ValueError("agent version must be a dotted semantic version")
        if len(set(self.capabilities)) != len(self.capabilities):
            raise ValueError("agent capabilities must be unique")
        if len(set(self.supported_stages)) != len(self.supported_stages):
            raise ValueError("agent supported stages must be unique")
