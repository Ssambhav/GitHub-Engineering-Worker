"""Protocols for GitHub integration dependency injection."""

from github.interfaces.protocols import GitHubClientProtocol, RepositoryWorkspaceProtocol

__all__ = ["GitHubClientProtocol", "RepositoryWorkspaceProtocol"]
