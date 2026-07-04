"""Protocol interfaces for provider and patch services."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from engineering.models.core import PatchApplicationResult, PatchResponse, PatchValidationResult, ProviderRequest


class AIProvider(Protocol):
    """AI provider abstraction."""

    name: str

    def generate_patch(self, request: ProviderRequest) -> PatchResponse: ...


class PatchValidatorProtocol(Protocol):
    """Patch validator abstraction."""

    def validate(self, repository_path: Path, diff: str) -> PatchValidationResult: ...


class PatchApplierProtocol(Protocol):
    """Patch applier abstraction."""

    def apply(self, repository_path: Path, diff: str, *, dry_run: bool = True) -> PatchApplicationResult: ...
