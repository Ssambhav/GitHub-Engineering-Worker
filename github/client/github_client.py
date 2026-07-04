"""Small stdlib GitHub REST client used by worker services."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from github.configuration import GitHubIntegrationConfig
from github.exceptions import (
    GitHubAuthenticationException,
    GitHubIntegrationException,
    IssueNotFoundException,
    PullRequestException,
    RepositoryNotFoundException,
)
from github.models import GitHubComment, GitHubIssue, GitHubRepository, PullRequestDraft


@dataclass(slots=True)
class GitHubClient:
    """Reusable client hiding GitHub API details from agents and tools."""

    config: GitHubIntegrationConfig
    last_rate_limit_remaining: int | None = None

    def validate_credentials(self) -> bool:
        """Return whether configured credentials can access the GitHub API."""

        if not self.config.token:
            return False
        self._request("GET", "/user", require_auth=True)
        return True

    def get_repository(self, owner: str, repo: str) -> GitHubRepository:
        """Read repository metadata."""

        data = self._request("GET", f"/repos/{owner}/{repo}")
        return self._repository_from_payload(data)

    def get_issue(self, owner: str, repo: str, issue_number: int) -> GitHubIssue:
        """Read and normalize one issue."""

        data = self._request("GET", f"/repos/{owner}/{repo}/issues/{issue_number}")
        return self._issue_from_payload(data)

    def list_open_issues(self, owner: str, repo: str, *, limit: int = 30) -> tuple[GitHubIssue, ...]:
        """List open issues, excluding pull requests."""

        params = {"state": "open", "per_page": max(1, min(limit, 100))}
        data = self._request("GET", f"/repos/{owner}/{repo}/issues?{urlencode(params)}")
        return tuple(self._issue_from_payload(item) for item in data if "pull_request" not in item)

    def list_issue_comments(self, owner: str, repo: str, issue_number: int) -> tuple[GitHubComment, ...]:
        """Read comments for an issue."""

        data = self._request("GET", f"/repos/{owner}/{repo}/issues/{issue_number}/comments")
        return tuple(
            GitHubComment(
                identifier=int(item["id"]),
                body=str(item.get("body") or ""),
                user_login=(item.get("user") or {}).get("login"),
                created_at=_parse_datetime(item.get("created_at")),
                updated_at=_parse_datetime(item.get("updated_at")),
            )
            for item in data
        )

    def list_labels(self, owner: str, repo: str) -> tuple[str, ...]:
        """Read repository label names."""

        data = self._request("GET", f"/repos/{owner}/{repo}/labels?per_page=100")
        return tuple(str(item["name"]) for item in data)

    def get_branch(self, owner: str, repo: str, branch: str) -> Mapping[str, Any]:
        """Read branch metadata."""

        return self._request("GET", f"/repos/{owner}/{repo}/branches/{branch}")

    def create_pull_request(
        self,
        owner: str,
        repo: str,
        *,
        title: str,
        body: str,
        head: str,
        base: str,
        draft: bool = False,
        dry_run: bool = False,
    ) -> PullRequestDraft:
        """Create or prepare a pull request."""

        if dry_run:
            return PullRequestDraft(title=title, body=body, head=head, base=base, dry_run=True)
        payload = {"title": title, "body": body, "head": head, "base": base, "draft": draft}
        data = self._request("POST", f"/repos/{owner}/{repo}/pulls", payload=payload, require_auth=True)
        return PullRequestDraft(
            title=title,
            body=body,
            head=head,
            base=base,
            html_url=data.get("html_url"),
            number=data.get("number"),
            dry_run=False,
        )

    def update_pull_request(
        self,
        owner: str,
        repo: str,
        pull_number: int,
        *,
        title: str | None = None,
        body: str | None = None,
        base: str | None = None,
        dry_run: bool = False,
    ) -> Mapping[str, Any]:
        """Update or prepare an update to a pull request."""

        payload = {key: value for key, value in {"title": title, "body": body, "base": base}.items() if value is not None}
        if dry_run:
            return {"dry_run": True, "pull_number": pull_number, "payload": payload}
        return self._request("PATCH", f"/repos/{owner}/{repo}/pulls/{pull_number}", payload=payload, require_auth=True)

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: Mapping[str, Any] | None = None,
        require_auth: bool = False,
    ) -> Any:
        if require_auth and not self.config.token:
            raise GitHubAuthenticationException(f"GitHub token is not configured in {self.config.token_env}")
        url = f"{self.config.api_base_url.rstrip('/')}/{path.lstrip('/')}"
        body = json.dumps(dict(payload)).encode("utf-8") if payload is not None else None
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": self.config.user_agent,
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.config.token:
            headers["Authorization"] = f"Bearer {self.config.token}"
        request = Request(url, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=30) as response:
                remaining = int(response.headers.get("X-RateLimit-Remaining", "100"))
                self.last_rate_limit_remaining = remaining
                text = response.read().decode("utf-8")
                return json.loads(text) if text else {}
        except HTTPError as exc:
            self._raise_http_error(exc, path)
        except URLError as exc:
            raise GitHubIntegrationException(f"GitHub request failed: {exc.reason}") from exc

    def _raise_http_error(self, exc: HTTPError, path: str) -> None:
        message = exc.read().decode("utf-8", errors="replace")
        if exc.code in {401, 403}:
            raise GitHubAuthenticationException(f"GitHub authentication failed for {path}: {message}") from exc
        if exc.code == 404 and "/issues/" in path:
            raise IssueNotFoundException(f"GitHub issue was not found: {path}") from exc
        if exc.code == 404 and "/repos/" in path:
            raise RepositoryNotFoundException(f"GitHub repository was not found: {path}") from exc
        if "/pulls" in path:
            raise PullRequestException(f"GitHub pull request request failed: HTTP {exc.code} {message}") from exc
        raise GitHubIntegrationException(f"GitHub request failed: HTTP {exc.code} {message}") from exc

    def _repository_from_payload(self, data: Mapping[str, Any]) -> GitHubRepository:
        return GitHubRepository(
            owner=str(data["owner"]["login"]),
            name=str(data["name"]),
            full_name=str(data["full_name"]),
            private=bool(data["private"]),
            default_branch=str(data["default_branch"]),
            clone_url=str(data["clone_url"]),
            ssh_url=str(data["ssh_url"]),
            html_url=str(data["html_url"]),
            description=data.get("description"),
            metadata={"id": data.get("id"), "visibility": data.get("visibility")},
        )

    def _issue_from_payload(self, data: Mapping[str, Any]) -> GitHubIssue:
        return GitHubIssue(
            number=int(data["number"]),
            title=str(data["title"]),
            state=str(data["state"]),
            body=data.get("body"),
            html_url=str(data["html_url"]),
            labels=tuple(str(label["name"]) for label in data.get("labels", ())),
            comments=int(data.get("comments", 0)),
            user_login=(data.get("user") or {}).get("login"),
            created_at=_parse_datetime(data.get("created_at")),
            updated_at=_parse_datetime(data.get("updated_at")),
            pull_request="pull_request" in data,
            metadata={"id": data.get("id"), "locked": data.get("locked")},
        )


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
