"""Pull request creation, updates, and body generation."""

from __future__ import annotations

from dataclasses import dataclass

from github.client import GitHubClient
from github.configuration import GitHubIntegrationConfig
from github.exceptions import PullRequestException
from github.models import PullRequestDraft


@dataclass(slots=True)
class PullRequestService:
    """Create and update pull requests with dry-run support."""

    config: GitHubIntegrationConfig
    client: GitHubClient

    def generate_body(self, *, issue_number: int, summary: str) -> str:
        """Generate a pull request body with an engineering summary and issue link."""

        return self.config.pr_body_template.format(issue_number=issue_number, summary=summary)

    def create_pr(
        self,
        owner: str,
        repo: str,
        *,
        issue_number: int,
        issue_title: str,
        summary: str,
        head: str,
        base: str,
        dry_run: bool = True,
        draft: bool = False,
    ) -> PullRequestDraft:
        """Create or dry-run a pull request."""

        title = self.config.pr_title_template.format(issue_number=issue_number, title=issue_title)
        body = self.generate_body(issue_number=issue_number, summary=summary)
        self.validate(title=title, body=body, head=head, base=base)
        return self.client.create_pull_request(
            owner,
            repo,
            title=title,
            body=body,
            head=head,
            base=base,
            draft=draft,
            dry_run=dry_run,
        )

    def update_pr(
        self,
        owner: str,
        repo: str,
        pull_number: int,
        *,
        title: str | None = None,
        body: str | None = None,
        base: str | None = None,
        dry_run: bool = True,
    ) -> object:
        """Update or dry-run an update to a pull request."""

        if pull_number < 1:
            raise PullRequestException("pull request number must be positive")
        return self.client.update_pull_request(owner, repo, pull_number, title=title, body=body, base=base, dry_run=dry_run)

    def validate(self, *, title: str, body: str, head: str, base: str) -> None:
        """Validate required pull request fields."""

        if not title.strip():
            raise PullRequestException("pull request title is required")
        if not body.strip():
            raise PullRequestException("pull request body is required")
        if not head.strip() or not base.strip():
            raise PullRequestException("pull request head and base are required")
