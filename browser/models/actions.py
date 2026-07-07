"""Strongly typed browser action result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class BrowserArtifact:
    """Artifact emitted by a browser action."""

    artifact_id: str
    kind: str
    path: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BrowserStorageState:
    """Serializable browser storage state."""

    cookies: tuple[Mapping[str, Any], ...] = ()
    local_storage: Mapping[str, Mapping[str, str]] = field(default_factory=dict)
    session_storage: Mapping[str, Mapping[str, str]] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PageSnapshot:
    """Current page metadata."""

    url: str
    title: str
    tab_id: str
    browser_type: str


@dataclass(frozen=True, slots=True)
class BrowserActionResult:
    """Result returned by every BrowserRuntime action."""

    success: bool
    action: str
    execution_time_ms: int
    url: str = ""
    page_title: str = ""
    data: Mapping[str, Any] = field(default_factory=dict)
    artifacts: tuple[BrowserArtifact, ...] = ()
    screenshots: tuple[BrowserArtifact, ...] = ()
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
