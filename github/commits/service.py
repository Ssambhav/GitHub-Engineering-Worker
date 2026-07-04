"""Commit message generation and commit workflow service."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from github.configuration import GitHubIntegrationConfig
from github.repositories import RepositoryOperations


@dataclass(slots=True)
class CommitService:
    """Stages files and creates commits with configured message templates."""

    config: GitHubIntegrationConfig
    operations: RepositoryOperations

    def generate_message(self, *, issue_number: int, title: str) -> str:
        """Generate a commit message from configuration."""

        return self.config.commit_message_template.format(issue_number=issue_number, title=title)

    def create_commit(
        self,
        path: Path,
        *,
        issue_number: int,
        title: str,
        files: tuple[str, ...] | None = None,
        allow_empty: bool = False,
    ) -> str:
        """Stage files and create a commit."""

        self.operations.stage_files(path, files)
        return self.operations.commit(path, self.generate_message(issue_number=issue_number, title=title), allow_empty=allow_empty)
