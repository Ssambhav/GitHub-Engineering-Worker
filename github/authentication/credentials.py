"""GitHub credential loading and validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from github.configuration import GitHubIntegrationConfig
from github.exceptions import GitHubAuthenticationException


class TokenValidator(Protocol):
    """Protocol for clients that can validate configured credentials."""

    def validate_credentials(self) -> bool:
        """Return true when credentials are accepted by GitHub."""


@dataclass(frozen=True, slots=True)
class GitHubAuthenticator:
    """Loads PAT credentials and validates them through a client."""

    config: GitHubIntegrationConfig

    def token(self, *, required: bool = False) -> str | None:
        """Return the configured token, raising if required and unavailable."""

        if self.config.token:
            return self.config.token
        if required:
            raise GitHubAuthenticationException(f"GitHub token is not configured in {self.config.token_env}")
        return None

    def validate(self, validator: TokenValidator) -> None:
        """Validate configured credentials against GitHub."""

        if not self.config.token:
            raise GitHubAuthenticationException(f"GitHub token is not configured in {self.config.token_env}")
        if not validator.validate_credentials():
            raise GitHubAuthenticationException("GitHub credentials were rejected")
