"""Tool metadata and capability models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from runtime.models.common import immutable_mapping


@dataclass(frozen=True, slots=True)
class ToolCapabilities:
    """Capability identifiers advertised by a tool."""

    values: tuple[str, ...]

    def contains(self, capability: str) -> bool:
        return capability in self.values


@dataclass(frozen=True, slots=True)
class ToolMetadata:
    """Production metadata for a registered tool."""

    identifier: str
    name: str
    version: str
    description: str
    capabilities: ToolCapabilities
    owner: str = "tools"
    side_effects: tuple[str, ...] = ("read",)
    idempotency: str = "idempotent"
    input_schema: Mapping[str, Any] = field(default_factory=immutable_mapping)
    output_schema: Mapping[str, Any] = field(default_factory=immutable_mapping)
    supported_versions: tuple[str, ...] = ()
    extra: Mapping[str, Any] = field(default_factory=immutable_mapping)

    def validate(self) -> None:
        if not self.identifier.strip():
            raise ValueError("tool identifier is required")
        if not self.name.strip():
            raise ValueError("tool name is required")
        if not self.version.strip():
            raise ValueError("tool version is required")
        if not self.capabilities.values:
            raise ValueError(f"tool capabilities are required: {self.identifier}")

    @property
    def capability_values(self) -> tuple[str, ...]:
        return self.capabilities.values
