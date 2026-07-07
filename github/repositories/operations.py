"""Local git repository operations used before issue solving starts."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from github.exceptions import BranchException, CommitException, WorkspaceException


@dataclass(frozen=True, slots=True)
class RepositoryOperations:
    """Repository-level git commands with structured exceptions."""

    def checkout_branch(self, path: Path, branch: str) -> None:
        """Check out an existing local or remote branch."""

        _run(path, ["checkout", branch], BranchException)

    def create_branch(self, path: Path, branch: str, *, base: str | None = None, reset_existing: bool = False) -> None:
        """Create and check out a branch from the current HEAD or a base ref."""

        if reset_existing:
            _run(path, ["checkout", "-B", branch, *( [base] if base else [] )], BranchException)
            return
        _run(path, ["checkout", "-b", branch, *( [base] if base else [] )], BranchException)

    def delete_branch(self, path: Path, branch: str, *, force: bool = False) -> None:
        """Delete a local branch."""

        _run(path, ["branch", "-D" if force else "-d", branch], BranchException)

    def current_branch(self, path: Path) -> str:
        """Return the current branch name."""

        return _run(path, ["branch", "--show-current"], WorkspaceException).stdout.strip()

    def changed_files(self, path: Path) -> tuple[str, ...]:
        """Return changed file paths from porcelain status."""

        output = _run(path, ["status", "--porcelain"], WorkspaceException).stdout
        return tuple(line[3:] for line in output.splitlines() if line)

    def validate_clean_working_tree(self, path: Path) -> None:
        """Raise when the working tree contains local changes."""

        changed = self.changed_files(path)
        if changed:
            raise WorkspaceException(f"working tree is not clean: {', '.join(changed)}")

    def validate_remote(self, path: Path, remote: str = "origin") -> str:
        """Return a remote URL or raise if the remote is missing."""

        return _run(path, ["remote", "get-url", remote], WorkspaceException).stdout.strip()

    def stage_files(self, path: Path, files: tuple[str, ...] | None = None) -> None:
        """Stage selected files or all changes."""

        _run(path, ["add", *(files or ("--all",))], CommitException)

    def commit(self, path: Path, message: str, *, allow_empty: bool = False) -> str:
        """Create a commit and return the new commit SHA."""

        args = ["commit", "-m", message]
        if allow_empty:
            args.insert(1, "--allow-empty")
        _run(path, args, CommitException)
        return _run(path, ["rev-parse", "HEAD"], CommitException).stdout.strip()

    def push_branch(self, path: Path, branch: str, *, remote: str = "origin", dry_run: bool = False) -> None:
        """Push a branch to a remote."""

        if dry_run:
            self.validate_remote(path, remote)
            _run(path, ["rev-parse", "--verify", branch], CommitException)
            return
        args = ["push", "-u", remote, branch]
        _run(path, args, CommitException)

    def rollback_last_commit(self, path: Path, *, keep_changes: bool = True) -> None:
        """Rollback the most recent commit."""

        _run(path, ["reset", "--soft" if keep_changes else "--hard", "HEAD~1"], CommitException)


def _run(path: Path, args: list[str], exception_type: type[Exception]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run([*_git_command(), *args], cwd=path, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise exception_type(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result


def _git_command() -> list[str]:
    if sys.platform.startswith("win"):
        return ["git", "-c", "http.sslBackend=schannel"]
    return ["git"]
