"""Tool execution service."""

from __future__ import annotations

from agents.contracts import RuntimeServices
from runtime.models.events import Event, EventCategory, EventSeverity
from tools.configuration import ToolConfiguration
from tools.context import ToolContext, ToolRequest
from tools.exceptions import ToolCancelledException, ToolException
from tools.registry import ToolRegistry
from tools.results import ToolResult


class ToolExecutor:
    """Executes tool requests through lifecycle, validation, memory, and events."""

    def __init__(self, registry: ToolRegistry, services: RuntimeServices, configuration: ToolConfiguration) -> None:
        self.registry = registry
        self.services = services
        self.configuration = configuration

    def execute(self, request: ToolRequest, context: ToolContext) -> ToolResult:
        self.registry.validate_version(request.tool_id, request.requested_version)
        tool = self.registry.get_implementation(request.tool_id)
        scoped_context = context.with_request(request)
        started = self._event("tool.started", scoped_context, {"tool_id": request.tool_id}, EventSeverity.INFO)
        self._publish(started)
        try:
            result = tool.run(request, scoped_context)
        except ToolCancelledException as exc:
            result = ToolResult.failure(
                metadata=tool.metadata,
                error=str(exc),
                execution_time_ms=0,
                structured_output={"cancelled": True},
            )
        except ToolException as exc:
            result = tool.recover(exc, scoped_context)
        except Exception as exc:
            result = tool.recover(exc, scoped_context)
        completed = self._event(
            "tool.completed" if result.success else "tool.failed",
            scoped_context,
            {"tool_id": request.tool_id, "status": result.status.value, "success": result.success},
            EventSeverity.INFO if result.success else EventSeverity.ERROR,
        )
        self._publish(completed)
        scoped_context.memory.propose_update(
            f"tool:{request.tool_id}:last_result",
            {"status": result.status.value, "success": result.success},
        )
        return result.with_events((started, completed))

    def create_context(self, execution_context, request: ToolRequest | None = None) -> ToolContext:
        return ToolContext(
            execution=execution_context,
            configuration=self.configuration,
            runtime_services=self.services,
            logger=self.services.logger,
            memory=self.services.memory,
            cancellation_token=execution_context.cancellation_token,
            request=request,
        )

    def _publish(self, event: Event) -> None:
        if self.services.event_bus is not None:
            self.services.event_bus.publish(event)

    def _event(self, event_type: str, context: ToolContext, payload, severity: EventSeverity) -> Event:
        return Event(
            event_type=event_type,
            category=EventCategory.TOOL,
            execution_id=context.execution.execution_id,
            correlation_id=context.execution.correlation_id,
            payload=payload,
            severity=severity,
            source="tools.executor",
        )
