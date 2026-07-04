"""Engineering tool base class and lifecycle defaults."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar, Mapping

from tools.context import ToolContext, ToolRequest
from tools.exceptions import ToolCancelledException, ToolValidationException
from tools.metadata import ToolMetadata
from tools.results import ToolResult


class EngineeringTool(ABC):
    """Base class for all external-action tools."""

    metadata: ClassVar[ToolMetadata]

    def initialize(self, context: ToolContext) -> None:
        context.logger.debug("tool initialized", tool_id=self.metadata.identifier)

    def validate(self, request: ToolRequest, context: ToolContext) -> None:
        if request.tool_id != self.metadata.identifier:
            raise ToolValidationException(f"request targets {request.tool_id}, expected {self.metadata.identifier}")
        for field_name in self.required_inputs():
            if field_name not in request.inputs:
                raise ToolValidationException(f"missing required input: {field_name}")
        context.configuration.validate()

    def prepare(self, request: ToolRequest, context: ToolContext) -> Mapping[str, Any]:
        _ = (request, context)
        return {}

    def finalize(self, result: ToolResult, context: ToolContext) -> ToolResult:
        context.logger.debug("tool finalized", tool_id=self.metadata.identifier, status=result.status.value)
        return result

    def cleanup(self, context: ToolContext) -> None:
        context.logger.debug("tool cleanup complete", tool_id=self.metadata.identifier)

    def cancel(self, context: ToolContext, reason: str | None = None) -> None:
        context.cancellation_token.cancel(reason or f"tool cancelled: {self.metadata.identifier}")

    def recover(self, error: Exception, context: ToolContext) -> ToolResult:
        return ToolResult.failure(
            metadata=self.metadata,
            error=str(error),
            execution_time_ms=0,
            structured_output={"recoverable": False},
        )

    def run(self, request: ToolRequest, context: ToolContext) -> ToolResult:
        """Run the full lifecycle around the implementation-specific execute step."""

        if context.cancellation_token.is_cancelled:
            raise ToolCancelledException(context.cancellation_token.reason or "tool cancelled")
        self.initialize(context)
        started = context.clock_ms()
        try:
            self.validate(request, context)
            prepared = self.prepare(request, context)
            result = self.execute(request, context, prepared)
            return self.finalize(result.with_execution_time(context.clock_ms() - started), context)
        finally:
            self.cleanup(context)

    @classmethod
    def required_inputs(cls) -> tuple[str, ...]:
        return ()

    @abstractmethod
    def execute(self, request: ToolRequest, context: ToolContext, prepared: Mapping[str, Any]) -> ToolResult:
        """Perform the bounded external action."""
