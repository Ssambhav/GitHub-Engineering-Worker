"""Safe local workspace management for GitHub repositories."""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from github.configuration import GitHubIntegrationConfig
from github.exceptions import RepositoryCloneException, WorkspaceException
from github.models import GitHubRepository, WorkspaceState


@dataclass(slots=True)
class RepositoryWorkspaceManager:
    """Owns clone locations, safe path handling, and repository refresh."""

    config: GitHubIntegrationConfig

    def clone_or_reuse(self, repository: GitHubRepository, *, temporary: bool = False) -> Path:
        """Clone a repository or reuse a valid existing clone."""

        root = self._workspace_root(temporary=temporary)
        target = self.repository_path(repository.full_name, temporary=temporary)
        root.mkdir(parents=True, exist_ok=True)
        if target.exists():
            self.validate_workspace(target, expected_remote=repository.clone_url)
            self.fetch(target)
            return target
        command = [*_git_command(), "clone", repository.clone_url, str(target)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RepositoryCloneException(result.stderr.strip() or "git clone failed")
        return target

    def repository_path(self, full_name: str, *, temporary: bool = False) -> Path:
        """Return a safe local path for a GitHub repository full name."""

        if "/" not in full_name:
            raise WorkspaceException(f"repository full name is invalid: {full_name}")
        owner, repo = full_name.split("/", 1)
        safe = Path(_safe_segment(owner)) / _safe_segment(repo)
        root = self._workspace_root(temporary=temporary)
        target = (root / safe).resolve()
        if root.resolve() not in (*target.parents, target):
            raise WorkspaceException(f"workspace path escapes root: {target}")
        return target

    def validate_workspace(self, path: Path, *, expected_remote: str | None = None) -> None:
        """Validate that a path is an existing git checkout with the expected remote."""

        if not path.exists() or not path.is_dir():
            raise WorkspaceException(f"workspace does not exist: {path}")
        if not (path / ".git").exists():
            raise WorkspaceException(f"workspace is not a git repository: {path}")
        if expected_remote:
            remote = self.remote_url(path)
            if remote not in {expected_remote, _tokenless_url(expected_remote)}:
                raise WorkspaceException(f"workspace remote mismatch: {remote}")

    def cleanup(self, path: Path, *, force: bool = False) -> None:
        """Clean up a workspace when policy allows it."""

        if self.config.cleanup_policy != "delete" and not force:
            return
        root = self.config.workspace_path.resolve()
        target = path.resolve()
        if root not in (*target.parents, target):
            raise WorkspaceException(f"refusing to remove path outside workspace root: {target}")
        shutil.rmtree(target)

    def fetch(self, path: Path) -> None:
        """Fetch remote refs for an existing clone."""

        _run_git(path, ["fetch", "--prune"], RepositoryCloneException)

    def refresh(self, path: Path, branch: str) -> None:
        """Fetch and pull the selected branch."""

        self.fetch(path)
        _run_git(path, ["checkout", branch], RepositoryCloneException)
        _run_git(path, ["pull", "--ff-only"], RepositoryCloneException)

    def status(self, path: Path, repository: str) -> WorkspaceState:
        """Return current branch, changed files, cleanliness, and remote."""

        current = _run_git(path, ["branch", "--show-current"], WorkspaceException).stdout.strip()
        status = _run_git(path, ["status", "--porcelain"], WorkspaceException).stdout
        changed = tuple(line[3:] for line in status.splitlines() if line)
        return WorkspaceState(
            path=path,
            repository=repository,
            current_branch=current,
            changed_files=changed,
            clean=not changed,
            remote_url=self.remote_url(path),
        )

    def remote_url(self, path: Path) -> str | None:
        """Return origin remote URL if configured."""

        result = subprocess.run([*_git_command(), "remote", "get-url", "origin"], cwd=path, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return None
        return _tokenless_url(result.stdout.strip())

    def _workspace_root(self, *, temporary: bool) -> Path:
        suffix = "tmp" if temporary else "persistent"
        return (self.config.workspace_path / suffix).resolve()


def _safe_segment(value: str) -> str:
    allowed = "".join(ch for ch in value if ch.isalnum() or ch in {"-", "_", "."})
    if not allowed or allowed in {".", ".."}:
        raise WorkspaceException(f"unsafe path segment: {value}")
    return allowed


def _tokenless_url(value: str) -> str:
    if "@github.com/" not in value:
        return value
    return f"https://github.com/{value.split('@github.com/', 1)[1]}"


def _run_git(
    path: Path,
    args: list[str],
    exception_type: type[Exception],
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run([*_git_command(), *args], cwd=path, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise exception_type(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result


def _git_command() -> list[str]:
    if sys.platform.startswith("win"):
        return ["git", "-c", "http.sslBackend=schannel"]
    return ["git"]
