"""Facade that prepares all GitHub data needed before issue resolution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from github.branches import BranchService
from github.client import GitHubClient
from github.commits import CommitService
from github.configuration import GitHubIntegrationConfig
from github.issues import IssueService
from github.models import GitHubIssue, GitHubRepository, PullRequestDraft, WorkspaceState
from github.pull_requests import PullRequestService
from github.repositories import RepositoryOperations
from github.workspace import RepositoryWorkspaceManager


@dataclass(slots=True)
class GitHubPreparationService:
    """Coordinates repository, issue, workspace, branch, commit, and PR preparation."""

    config: GitHubIntegrationConfig
    client: GitHubClient
    workspace: RepositoryWorkspaceManager
    repository_operations: RepositoryOperations
    issues: IssueService
    branches: BranchService
    commits: CommitService
    pull_requests: PullRequestService

    @classmethod
    def create(cls, config: GitHubIntegrationConfig) -> "GitHubPreparationService":
        """Build the service graph with dependency injection defaults."""

        client = GitHubClient(config)
        operations = RepositoryOperations()
        return cls(
            config=config,
            client=client,
            workspace=RepositoryWorkspaceManager(config),
            repository_operations=operations,
            issues=IssueService(client),
            branches=BranchService(config, operations),
            commits=CommitService(config, operations),
            pull_requests=PullRequestService(config, client),
        )

    def prepare_repository(self, owner: str, repo: str, *, temporary: bool = False) -> tuple[GitHubRepository, Path]:
        """Read repository metadata and clone or reuse the local workspace."""

        repository = self.client.get_repository(owner, repo)
        return repository, self.workspace.clone_or_reuse(repository, temporary=temporary)

    def read_issue_context(self, owner: str, repo: str, issue_number: int) -> GitHubIssue:
        """Read normalized issue data."""

        return self.issues.read_issue(owner, repo, issue_number)

    def create_issue_branch(self, path: Path, issue: GitHubIssue, *, base: str) -> str:
        """Create a local issue branch."""

        return self.branches.create_issue_branch(path, issue_number=issue.number, title=issue.title, base=base)

    def create_sample_commit(self, path: Path, issue: GitHubIssue) -> str:
        """Create an empty marker commit for integration verification only."""

        return self.commits.create_commit(path, issue_number=issue.number, title=issue.title, allow_empty=True)

    def status(self, path: Path, repository: str) -> WorkspaceState:
        """Return workspace status."""

        return self.workspace.status(path, repository)

    def dry_run_pull_request(
        self,
        owner: str,
        repo: str,
        issue: GitHubIssue,
        *,
        head: str,
        base: str,
        summary: str,
    ) -> PullRequestDraft:
        """Exercise pull request creation without writing to GitHub."""

        return self.pull_requests.create_pr(
            owner,
            repo,
            issue_number=issue.number,
            issue_title=issue.title,
            summary=summary,
            head=head,
            base=base,
            dry_run=True,
        )
