"""Dataclasses for normalized GitHub and git repository data."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class GitHubRepository:
    """Normalized GitHub repository metadata."""

    owner: str
    name: str
    full_name: str
    private: bool
    default_branch: str
    clone_url: str
    ssh_url: str
    html_url: str
    description: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GitHubIssue:
    """Normalized GitHub issue payload."""

    number: int
    title: str
    state: str
    body: str | None
    html_url: str
    labels: tuple[str, ...]
    comments: int
    user_login: str | None
    created_at: datetime | None
    updated_at: datetime | None
    pull_request: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GitHubComment:
    """Normalized GitHub issue comment."""

    identifier: int
    body: str
    user_login: str | None
    created_at: datetime | None
    updated_at: datetime | None


@dataclass(frozen=True, slots=True)
class PullRequestDraft:
    """Prepared or created pull request details."""

    title: str
    body: str
    head: str
    base: str
    html_url: str | None = None
    number: int | None = None
    dry_run: bool = False


@dataclass(frozen=True, slots=True)
class WorkspaceState:
    """Local repository workspace state."""

    path: Path
    repository: str
    current_branch: str
    changed_files: tuple[str, ...]
    clean: bool
    remote_url: str | None
