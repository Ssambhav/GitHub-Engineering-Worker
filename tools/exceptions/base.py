"""Exception hierarchy for tool runtime failures."""


class ToolException(Exception):
    """Base exception for tool runtime failures."""


class ToolExecutionException(ToolException):
    """Raised when a tool action fails during execution."""


class ToolValidationException(ToolException):
    """Raised when a tool request or output is invalid."""


class ToolConfigurationException(ToolException):
    """Raised for invalid tool configuration."""


class ToolCancelledException(ToolException):
    """Raised when a tool invocation is cancelled."""


class ToolRegistryException(ToolException):
    """Raised for registry and discovery failures."""
