"""Branch naming and creation service."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from github.configuration import GitHubIntegrationConfig
from github.repositories import RepositoryOperations


@dataclass(slots=True)
class BranchService:
    """Creates repository-independent branch names and local branches."""

    config: GitHubIntegrationConfig
    operations: RepositoryOperations

    def generate_name(self, *, issue_number: int, title: str) -> str:
        """Generate a safe branch name from the configured template."""

        slug = re.sub(r"[^a-z0-9._-]+", "-", title.lower()).strip("-")[:48] or "work"
        return self.config.branch_naming_template.format(issue_number=issue_number, title=title, slug=slug)

    def create_issue_branch(self, path: Path, *, issue_number: int, title: str, base: str) -> str:
        """Create and check out an issue preparation branch."""

        branch = self.generate_name(issue_number=issue_number, title=title)
        self.operations.create_branch(path, branch, base=base, reset_existing=True)
        return branch
