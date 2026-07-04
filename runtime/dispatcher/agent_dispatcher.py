"""Agent dispatcher implementation."""

from __future__ import annotations

from runtime.context import ExecutionContext
from runtime.exceptions import DispatchException
from runtime.interfaces import Agent
from runtime.models.agent import AgentResult, AgentTask
from runtime.registry import RuntimeRegistry


class RegisteredAgentDispatcher:
    """Dispatches tasks to agent implementations registered in RuntimeRegistry."""

    def __init__(self, registry: RuntimeRegistry) -> None:
        self.registry = registry

    def dispatch(self, task: AgentTask, context: ExecutionContext) -> AgentResult:
        context.cancellation_token.throw_if_cancelled()
        implementation = self.registry.agents.get_implementation(task.agent_id)
        if not _is_agent(implementation):
            raise DispatchException(f"Registered implementation is not an agent: {task.agent_id}")

        try:
            result = implementation.execute(task, context)
        except Exception as exc:
            raise DispatchException(
                f"Agent dispatch failed: {task.agent_id}",
                details={"agent_id": task.agent_id, "task_id": task.task_id},
            ) from exc

        if result.task_id != task.task_id or result.agent_id != task.agent_id:
            raise DispatchException(
                "Agent result does not match dispatched task",
                details={"task_id": task.task_id, "agent_id": task.agent_id},
            )
        return result


def _is_agent(value: object) -> bool:
    return isinstance(value, Agent)
