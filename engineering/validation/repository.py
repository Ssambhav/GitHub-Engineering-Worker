"""Repository integrity and patch consistency validation."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RepositoryValidator:
    """Validates git repository integrity and modified file status."""

    def validate(self, repository_path: Path, modified_files: tuple[str, ...]) -> tuple[str, ...]:
        warnings: list[str] = []
        if not (repository_path / ".git").exists():
            warnings.append("repository is not a git checkout")
        status = subprocess.run(["git", "status", "--porcelain"], cwd=repository_path, capture_output=True, text=True)
        if status.returncode != 0:
            warnings.append(status.stderr.strip() or "unable to inspect repository status")
        missing = [file_name for file_name in modified_files if not (repository_path / file_name).exists()]
        if missing:
            warnings.append(f"modified files missing after patch: {', '.join(missing)}")
        return tuple(warnings)
