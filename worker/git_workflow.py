"""Git workflow for autonomous issue completion."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from github.branches import BranchService
from github.commits import CommitService
from github.configuration import GitHubIntegrationConfig
from github.models import PullRequestDraft
from github.pull_requests import PullRequestService
from github.repositories import RepositoryOperations


@dataclass(frozen=True, slots=True)
class GitWorkflowResult:
    branch: str
    commit_sha: str | None
    pushed: bool
    pull_request: PullRequestDraft | None
    dry_run: bool


@dataclass(slots=True)
class GitWorkflow:
    """Creates feature branches, commits, pushes, and pull requests."""

    config: GitHubIntegrationConfig
    operations: RepositoryOperations
    branch_service: BranchService
    commit_service: CommitService
    pull_request_service: PullRequestService

    @classmethod
    def create(cls, config: GitHubIntegrationConfig, pull_request_service: PullRequestService) -> "GitWorkflow":
        operations = RepositoryOperations()
        return cls(
            config=config,
            operations=operations,
            branch_service=BranchService(config, operations),
            commit_service=CommitService(config, operations),
            pull_request_service=pull_request_service,
        )

    def complete_issue(
        self,
        *,
        path: Path,
        owner: str,
        repo: str,
        issue_number: int,
        issue_title: str,
        base_branch: str,
        summary: str,
        auto_commit: bool,
        auto_push: bool,
        auto_create_pr: bool,
        dry_run_remote: bool,
        auto_cleanup: bool,
    ) -> GitWorkflowResult:
        current = self.operations.current_branch(path)
        if current == base_branch:
            branch = self.branch_service.create_issue_branch(path, issue_number=issue_number, title=issue_title, base=base_branch)
        else:
            branch = current
        if branch == base_branch:
            raise ValueError("refusing to commit directly to the default branch")

        changed = self.operations.changed_files(path)
        commit_sha = None
        if auto_commit and changed:
            commit_sha = self.commit_service.create_commit(path, issue_number=issue_number, title=issue_title, files=changed)

        pushed = False
        if auto_push and commit_sha:
            self.operations.push_branch(path, branch, dry_run=dry_run_remote)
            pushed = True

        pull_request = None
        if auto_create_pr and (commit_sha or dry_run_remote):
            pull_request = self.pull_request_service.create_pr(
                owner,
                repo,
                issue_number=issue_number,
                issue_title=issue_title,
                summary=summary,
                head=branch,
                base=base_branch,
                dry_run=dry_run_remote,
            )

        if auto_cleanup and dry_run_remote and branch != base_branch:
            self.operations.checkout_branch(path, base_branch)
            self.operations.delete_branch(path, branch, force=True)

        return GitWorkflowResult(branch=branch, commit_sha=commit_sha, pushed=pushed, pull_request=pull_request, dry_run=dry_run_remote)
