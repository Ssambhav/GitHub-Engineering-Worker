"""GitHub issue read and normalization service."""

from __future__ import annotations

from dataclasses import dataclass

from github.client import GitHubClient
from github.exceptions import IssueNotFoundException
from github.models import GitHubComment, GitHubIssue


@dataclass(slots=True)
class IssueService:
    """Read issue metadata without attempting to solve issues."""

    client: GitHubClient

    def read_issue(self, owner: str, repo: str, issue_number: int) -> GitHubIssue:
        """Read and validate an issue."""

        issue = self.client.get_issue(owner, repo, issue_number)
        self.validate_issue(issue)
        return issue

    def list_open_issues(self, owner: str, repo: str, *, limit: int = 30) -> tuple[GitHubIssue, ...]:
        """List open issues."""

        return self.client.list_open_issues(owner, repo, limit=limit)

    def read_comments(self, owner: str, repo: str, issue_number: int) -> tuple[GitHubComment, ...]:
        """Read issue comments."""

        return self.client.list_issue_comments(owner, repo, issue_number)

    def read_labels(self, owner: str, repo: str) -> tuple[str, ...]:
        """Read repository labels."""

        return self.client.list_labels(owner, repo)

    def create_issue(
        self,
        owner: str,
        repo: str,
        *,
        title: str,
        body: str,
        labels: tuple[str, ...] = (),
        dry_run: bool = False,
    ) -> GitHubIssue:
        """Create an issue or return a dry-run issue when remote writes are disabled."""

        issue = self.client.create_issue(owner, repo, title=title, body=body, labels=labels, dry_run=dry_run)
        self.validate_issue(issue) if not dry_run else None
        return issue

    def validate_issue(self, issue: GitHubIssue) -> None:
        """Reject pull requests or invalid issue numbers when an issue is required."""

        if issue.number < 1:
            raise IssueNotFoundException(f"invalid issue number: {issue.number}")
        if issue.pull_request:
            raise IssueNotFoundException(f"#{issue.number} is a pull request, not an issue")
