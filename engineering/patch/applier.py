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
            apply_args = ["git", "apply", str(patch_path)]
            check_commands = (
                (["git", "apply", "--check", str(patch_path)], ["git", "apply", str(patch_path)]),
                (["git", "apply", "--check", "--recount", str(patch_path)], ["git", "apply", "--recount", str(patch_path)]),
                (
                    ["git", "apply", "--check", "--recount", "--ignore-whitespace", str(patch_path)],
                    ["git", "apply", "--recount", "--ignore-whitespace", str(patch_path)],
                ),
            )
            check = subprocess.run(check_commands[0][0], cwd=repository_path, capture_output=True, text=True)
            if check.returncode != 0:
                selected_apply = None
                for check_command, candidate_apply in check_commands[1:]:
                    fallback_check = subprocess.run(check_command, cwd=repository_path, capture_output=True, text=True)
                    if fallback_check.returncode == 0:
                        selected_apply = candidate_apply
                        break
                if selected_apply is None:
                    return PatchApplicationResult(False, dry_run, files, errors=(check.stderr.strip(),))
                apply_args = selected_apply
            if dry_run:
                return PatchApplicationResult(True, True, files)
            for file_name in files:
                source = repository_path / file_name
                if source.exists():
                    backup = source.with_suffix(source.suffix + ".gew.bak")
                    shutil.copy2(source, backup)
                    backups.append(backup)
            apply_result = subprocess.run(apply_args, cwd=repository_path, capture_output=True, text=True)
            if apply_result.returncode != 0:
                if atomic:
                    self.rollback(backups)
                return PatchApplicationResult(False, False, files, backups=tuple(backups), errors=(apply_result.stderr.strip(),))
            for backup in backups:
                backup.unlink(missing_ok=True)
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
