"""Agent exception hierarchy."""

from __future__ import annotations

from typing import Any, Mapping


class AgentExecutionException(Exception):
    """Raised when an agent lifecycle stage cannot complete."""

    def __init__(self, message: str, *, details: Mapping[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = dict(details or {})


class AgentValidationException(AgentExecutionException):
    """Raised when task inputs or produced outputs are invalid."""


class AgentConfigurationException(AgentExecutionException):
    """Raised when an agent configuration is invalid."""


class AgentInitializationException(AgentExecutionException):
    """Raised when an agent cannot initialize."""


class AgentCancelledException(AgentExecutionException):
    """Raised when cancellation is requested during execution."""
