"""Exception hierarchy for browser automation."""


class BrowserRuntimeError(Exception):
    """Raised when browser automation cannot complete."""


class BrowserConfigurationError(BrowserRuntimeError):
    """Raised for invalid browser automation configuration."""


class BrowserSafetyError(BrowserRuntimeError):
    """Raised when a browser action violates configured safety controls."""
