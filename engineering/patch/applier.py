"""Safe patch application with dry-run, backup, and rollback support."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

from engineering.models.core import PatchApplicationResult


@dataclass(frozen=True, slots=True)
class PatchApplier:
    """Applies unified diffs through git apply."""

    def apply(self, repository_path: Path, diff: str, *, dry_run: bool = True, atomic: bool = True) -> PatchApplicationResult:
        files = _modified_files(diff)
        with NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".patch") as handle:
            handle.write(diff)
            patch_path = Path(handle.name)
        backups: list[Path] = []
        try:
            check = subprocess.run(["git", "apply", "--check", str(patch_path)], cwd=repository_path, capture_output=True, text=True)
            if check.returncode != 0:
                return PatchApplicationResult(False, dry_run, files, errors=(check.stderr.strip(),))
            if dry_run:
                return PatchApplicationResult(True, True, files)
            for file_name in files:
                source = repository_path / file_name
                if source.exists():
                    backup = source.with_suffix(source.suffix + ".gew.bak")
                    shutil.copy2(source, backup)
                    backups.append(backup)
            apply_result = subprocess.run(["git", "apply", str(patch_path)], cwd=repository_path, capture_output=True, text=True)
            if apply_result.returncode != 0:
                if atomic:
                    self.rollback(backups)
                return PatchApplicationResult(False, False, files, backups=tuple(backups), errors=(apply_result.stderr.strip(),))
            return PatchApplicationResult(True, False, files, backups=tuple(backups))
        finally:
            patch_path.unlink(missing_ok=True)

    def rollback(self, backups: list[Path] | tuple[Path, ...]) -> None:
        """Restore backups created before application."""

        for backup in backups:
            target = Path(str(backup).removesuffix(".gew.bak"))
            if backup.exists():
                shutil.copy2(backup, target)


def _modified_files(diff: str) -> tuple[str, ...]:
    return tuple(line[6:] for line in diff.splitlines() if line.startswith("+++ b/"))
