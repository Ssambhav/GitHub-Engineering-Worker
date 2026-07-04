"""Interface contracts for GitHub services."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from github.models import GitHubIssue, GitHubRepository, PullRequestDraft, WorkspaceState


class GitHubClientProtocol(Protocol):
    """Protocol implemented by GitHub API clients."""

    def get_repository(self, owner: str, repo: str) -> GitHubRepository: ...

    def get_issue(self, owner: str, repo: str, issue_number: int) -> GitHubIssue: ...

    def list_open_issues(self, owner: str, repo: str, *, limit: int = 30) -> tuple[GitHubIssue, ...]: ...

    def create_pull_request(
        self,
        owner: str,
        repo: str,
        *,
        title: str,
        body: str,
        head: str,
        base: str,
        draft: bool = False,
        dry_run: bool = False,
    ) -> PullRequestDraft: ...


class RepositoryWorkspaceProtocol(Protocol):
    """Protocol implemented by local repository workspace managers."""

    def clone_or_reuse(self, repository: GitHubRepository) -> Path: ...

    def status(self, path: Path, repository: str) -> WorkspaceState: ...
