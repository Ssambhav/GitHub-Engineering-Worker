"""Protocols for tool runtime collaborators."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Mapping, Protocol

from tools.context import ToolContext, ToolRequest
from tools.metadata import ToolMetadata
from tools.results import ToolResult


class ToolLifecycle(Protocol):
    def initialize(self, context: ToolContext) -> None: ...

    def validate(self, request: ToolRequest, context: ToolContext) -> None: ...

    def prepare(self, request: ToolRequest, context: ToolContext) -> Mapping[str, object]: ...

    def execute(self, request: ToolRequest, context: ToolContext, prepared: Mapping[str, object]) -> ToolResult: ...

    def finalize(self, result: ToolResult, context: ToolContext) -> ToolResult: ...

    def cleanup(self, context: ToolContext) -> None: ...


class ToolDiscovery(Protocol):
    def discover(self, *, capability: str | None = None) -> Iterable[ToolMetadata]: ...

    def get(self, identifier: str) -> ToolMetadata: ...


class ToolValidation(Protocol):
    def validate_request(self, request: ToolRequest) -> None: ...

    def validate_metadata(self, metadata: ToolMetadata) -> None: ...
