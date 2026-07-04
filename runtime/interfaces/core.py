"""Protocol definitions for runtime components."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any, Protocol, TypeVar, runtime_checkable

from runtime.models.agent import AgentResult, AgentTask
from runtime.models.events import Event

T = TypeVar("T")


class ExecutionContextProtocol(Protocol):
    """Minimal execution context protocol."""

    execution_id: object
    current_stage: object
    current_state: object


@runtime_checkable
class Agent(Protocol):
    """Agent adapter contract used by the dispatcher."""

    @property
    def agent_id(self) -> str: ...

    def execute(self, task: AgentTask, context: ExecutionContextProtocol) -> AgentResult: ...


class AgentDispatcher(Protocol):
    """Dispatches tasks to registered agents."""

    def dispatch(self, task: AgentTask, context: ExecutionContextProtocol) -> AgentResult: ...


class Scheduler(Protocol):
    """Schedules units of runtime work."""

    def submit(self, operation: Callable[[], T]) -> T: ...


class EventBus(Protocol):
    """Internal event bus contract."""

    def publish(self, event: Event) -> None: ...

    def subscribe(self, event_type: str, handler: Callable[[Event], None]) -> str: ...

    def unsubscribe(self, subscription_id: str) -> bool: ...


class Registry(Protocol[T]):
    """Generic registry contract."""

    def register(self, metadata: T, implementation: Any | None = None) -> None: ...

    def get(self, identifier: str) -> T: ...

    def discover(self, *, capability: str | None = None) -> Iterable[T]: ...


class ConfigurationProvider(Protocol):
    """Loads typed runtime configuration."""

    def load(self) -> object: ...


class Session(Protocol):
    """Runtime session contract."""

    @property
    def session_id(self) -> str: ...

    def close(self) -> None: ...


class Lifecycle(Protocol):
    """Lifecycle manager contract."""

    def initialize(self) -> None: ...

    def shutdown(self, reason: str | None = None) -> None: ...


class Runtime(Protocol):
    """Execution runtime contract."""

    def start(self) -> None: ...

    def shutdown(self, reason: str | None = None) -> None: ...


class StructuredLogger(Protocol):
    """Structured logging contract. Providers are intentionally external."""

    def bind(self, **fields: object) -> "StructuredLogger": ...

    def debug(self, message: str, **fields: object) -> None: ...

    def info(self, message: str, **fields: object) -> None: ...

    def warning(self, message: str, **fields: object) -> None: ...

    def error(self, message: str, **fields: object) -> None: ...
