"""Tool registry integrated with the runtime registry."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Type

from runtime.models.registry import ToolMetadata as RuntimeToolMetadata
from runtime.registry import RuntimeRegistry
from tools.base import EngineeringTool
from tools.exceptions import ToolRegistryException
from tools.metadata import ToolMetadata


class ToolRegistry:
    """Registers tool metadata and implementations with duplicate validation."""

    def __init__(self, runtime_registry: RuntimeRegistry) -> None:
        self.runtime_registry = runtime_registry

    def register(self, tool_type: Type[EngineeringTool]) -> None:
        metadata = tool_type.metadata
        self.validate_metadata(metadata)
        if self.runtime_registry.tools.contains(metadata.identifier):
            raise ToolRegistryException(f"tool already registered: {metadata.identifier}")
        self.runtime_registry.tools.register(self._to_runtime_metadata(metadata), tool_type())

    def get(self, identifier: str) -> ToolMetadata:
        runtime_metadata = self.runtime_registry.tools.get(identifier)
        return self._from_runtime_metadata(runtime_metadata)

    def get_implementation(self, identifier: str) -> EngineeringTool:
        implementation = self.runtime_registry.tools.get_implementation(identifier)
        if not isinstance(implementation, EngineeringTool):
            raise ToolRegistryException(f"registered implementation is not an EngineeringTool: {identifier}")
        return implementation

    def discover(self, *, capability: str | None = None) -> Iterable[ToolMetadata]:
        return tuple(self._from_runtime_metadata(item) for item in self.runtime_registry.tools.discover(capability=capability))

    def by_capability(self, capability: str) -> tuple[ToolMetadata, ...]:
        return tuple(self.discover(capability=capability))

    def validate_version(self, identifier: str, requested_version: str | None) -> None:
        metadata = self.get(identifier)
        if requested_version is None:
            return
        allowed = metadata.supported_versions or (metadata.version,)
        if requested_version not in allowed:
            raise ToolRegistryException(f"unsupported version {requested_version} for {identifier}")

    def validate_metadata(self, metadata: ToolMetadata) -> None:
        try:
            metadata.validate()
        except ValueError as exc:
            raise ToolRegistryException(str(exc)) from exc

    def _to_runtime_metadata(self, metadata: ToolMetadata) -> RuntimeToolMetadata:
        return RuntimeToolMetadata(
            identifier=metadata.identifier,
            name=metadata.name,
            version=metadata.version,
            description=metadata.description,
            capabilities=metadata.capability_values,
            owner=metadata.owner,
            side_effects=metadata.side_effects,
            idempotency=metadata.idempotency,
            metadata={"tool_metadata": metadata},
        )

    def _from_runtime_metadata(self, metadata: RuntimeToolMetadata) -> ToolMetadata:
        tool_metadata = metadata.metadata.get("tool_metadata")
        if isinstance(tool_metadata, ToolMetadata):
            return tool_metadata
        raise ToolRegistryException(f"runtime metadata missing tool metadata: {metadata.identifier}")
