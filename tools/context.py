"""Strongly typed context passed to tools."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Mapping

from agents.contracts import MemoryAccess, NullMemoryAccess, NullStructuredLogger, RuntimeServices
from runtime.context import ExecutionContext
from runtime.interfaces import StructuredLogger
from runtime.models.common import CancellationToken, immutable_mapping
from tools.configuration import ToolConfiguration


@dataclass(frozen=True, slots=True)
class ToolRequest:
    """Request envelope for a tool invocation."""

    tool_id: str
    inputs: Mapping[str, Any] = field(default_factory=immutable_mapping)
    capability: str | None = None
    requested_version: str | None = None
    correlation_key: str | None = None


@dataclass(frozen=True, slots=True)
class ToolContext:
    """Runtime services and execution state available to a tool."""

    execution: ExecutionContext
    configuration: ToolConfiguration
    runtime_services: RuntimeServices
    logger: StructuredLogger = field(default_factory=NullStructuredLogger)
    memory: MemoryAccess = field(default_factory=NullMemoryAccess)
    cancellation_token: CancellationToken | None = None
    request: ToolRequest | None = None

    def __post_init__(self) -> None:
        if self.cancellation_token is None:
            object.__setattr__(self, "cancellation_token", self.execution.cancellation_token)

    def with_request(self, request: ToolRequest) -> "ToolContext":
        return ToolContext(
            execution=self.execution,
            configuration=self.configuration,
            runtime_services=self.runtime_services,
            logger=self.logger,
            memory=self.memory,
            cancellation_token=self.cancellation_token,
            request=request,
        )

    def clock_ms(self) -> int:
        return int(perf_counter() * 1000)
