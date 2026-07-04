"""Strongly typed configuration for GitHub repository preparation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True, slots=True)
class GitHubIntegrationConfig:
    """Configuration consumed by GitHub API and workspace services."""

    token_env: str = "GITHUB_TOKEN"
    token: str | None = None
    api_base_url: str = "https://api.github.com"
    workspace_path: Path = Path(".workspaces")
    branch_naming_template: str = "gew/issue-{issue_number}-{slug}"
    commit_message_template: str = "Fix issue #{issue_number}: {title}"
    pr_title_template: str = "Fix issue #{issue_number}: {title}"
    pr_body_template: str = "{summary}\n\nCloses #{issue_number}"
    cleanup_policy: str = "keep"
    rate_limit_threshold: int = 25
    user_agent: str = "github-engineering-worker"

    @classmethod
    def from_environment(
        cls,
        *,
        environment: Mapping[str, str] | None = None,
        token_env: str = "GITHUB_TOKEN",
        workspace_path: Path | str = Path(".workspaces"),
        branch_naming_template: str = "gew/issue-{issue_number}-{slug}",
        commit_message_template: str = "Fix issue #{issue_number}: {title}",
        pr_body_template: str = "{summary}\n\nCloses #{issue_number}",
        cleanup_policy: str = "keep",
        rate_limit_threshold: int = 25,
    ) -> "GitHubIntegrationConfig":
        env = environment or os.environ
        return cls(
            token_env=token_env,
            token=env.get(token_env),
            workspace_path=Path(workspace_path),
            branch_naming_template=branch_naming_template,
            commit_message_template=commit_message_template,
            pr_body_template=pr_body_template,
            cleanup_policy=cleanup_policy,
            rate_limit_threshold=rate_limit_threshold,
        )

    @property
    def has_token(self) -> bool:
        """Return whether a token is configured."""

        return bool(self.token)
