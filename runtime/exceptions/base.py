"""Runtime exception hierarchy."""

from __future__ import annotations


class RuntimeException(Exception):
    """Base class for runtime-level failures.

    Args:
        message: Human-readable diagnostic.
        code: Stable machine-readable error code.
        details: Optional structured details safe for logs or audit refs.
    """

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.__class__.__name__
        self.details = details or {}


class WorkflowException(RuntimeException):
    """Raised when workflow execution or transition coordination fails."""


class DispatchException(RuntimeException):
    """Raised when an agent cannot be dispatched or returns invalid output."""


class AgentException(RuntimeException):
    """Raised by agent adapters for agent-owned failures."""


class ConfigurationException(RuntimeException):
    """Raised when runtime configuration is missing or invalid."""


class ValidationException(RuntimeException):
    """Raised when typed runtime inputs or artifacts fail validation."""


class ExecutionCancelledException(RuntimeException):
    """Raised when execution is cancelled before completion."""


class RegistryException(RuntimeException):
    """Raised when registry registration, lookup, or validation fails."""

