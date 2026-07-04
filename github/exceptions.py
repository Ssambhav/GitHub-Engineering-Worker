"""GitHub and local workspace exception hierarchy."""

from __future__ import annotations


class GitHubIntegrationException(Exception):
    """Base exception for GitHub integration failures."""


class GitHubAuthenticationException(GitHubIntegrationException):
    """Raised when GitHub credentials are missing, invalid, or unauthorized."""


class RepositoryCloneException(GitHubIntegrationException):
    """Raised when cloning or refreshing a repository fails."""


class RepositoryNotFoundException(GitHubIntegrationException):
    """Raised when a GitHub repository cannot be found or accessed."""


class IssueNotFoundException(GitHubIntegrationException):
    """Raised when a GitHub issue cannot be found or accessed."""


class BranchException(GitHubIntegrationException):
    """Raised for local or remote branch operation failures."""


class CommitException(GitHubIntegrationException):
    """Raised for staging, commit, rollback, or push failures."""


class PullRequestException(GitHubIntegrationException):
    """Raised for pull request validation or API failures."""


class WorkspaceException(GitHubIntegrationException):
    """Raised when workspace paths or repositories are unsafe or invalid."""
