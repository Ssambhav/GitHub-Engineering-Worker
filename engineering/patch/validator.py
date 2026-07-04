"""Unified diff validation before application."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from engineering.configuration import EngineeringConfiguration
from engineering.models.core import PatchValidationResult


@dataclass(slots=True)
class PatchValidator:
    """Rejects malformed, unsafe, oversized, or unsupported patches."""

    config: EngineeringConfiguration

    def validate(self, repository_path: Path, diff: str) -> PatchValidationResult:
        errors: list[str] = []
        warnings: list[str] = []
        if not diff.strip():
            errors.append("diff is empty")
        if "--- " not in diff or "+++ " not in diff or "@@" not in diff:
            errors.append("diff is not valid unified diff format")
        files = tuple(dict.fromkeys(re.findall(r"^\+\+\+ b/(.+)$", diff, re.MULTILINE)))
        if len(files) > self.config.max_patch_changed_files:
            errors.append("patch modifies too many files")
        for file_name in files:
            path = (repository_path / file_name).resolve()
            if repository_path.resolve() not in (*path.parents, path):
                errors.append(f"unsafe path escapes repository: {file_name}")
            if any(part in {"node_modules", "vendor", "dist", "build", ".git"} for part in Path(file_name).parts):
                errors.append(f"unsafe generated/vendor path: {file_name}")
            if not path.exists():
                warnings.append(f"patch creates or references missing file: {file_name}")
        additions = sum(1 for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++"))
        deletions = sum(1 for line in diff.splitlines() if line.startswith("-") and not line.startswith("---"))
        if additions + deletions > self.config.max_patch_changed_lines:
            errors.append("patch changes too many lines")
        duplicates = [file_name for file_name in files if files.count(file_name) > 1]
        if duplicates:
            warnings.append(f"patch contains repeated file sections: {', '.join(sorted(set(duplicates)))}")
        return PatchValidationResult(
            valid=not errors,
            errors=tuple(errors),
            warnings=tuple(warnings),
            modified_files=files,
            additions=additions,
            deletions=deletions,
        )
