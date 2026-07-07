"""Protocols for browser automation implementations."""

from __future__ import annotations

from typing import Any, Mapping, Protocol

from browser.models import BrowserActionResult


class BrowserRuntimeProtocol(Protocol):
    """Minimal contract implemented by BrowserRuntime."""

    def perform(self, action: str, inputs: Mapping[str, Any]) -> BrowserActionResult:
        """Execute a browser action."""

    def shutdown(self) -> BrowserActionResult:
        """Close browser resources."""
