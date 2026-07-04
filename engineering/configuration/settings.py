"""Configuration for search, context, providers, patches, and tests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class EngineeringConfiguration:
    """Strongly typed engineering execution settings."""

    provider: str = "auto"
    model: str | None = None
    openai_api_key_env: str = "OPENAI_API_KEY"
    openrouter_api_key_env: str = "OPENROUTER_API_KEY"
    max_candidate_files: int = 12
    max_files_to_read: int = 6
    max_file_bytes: int = 24_000
    max_context_bytes: int = 80_000
    max_patch_changed_files: int = 24
    max_patch_changed_lines: int = 2_000
    workspace_root: Path = Path(".")
    test_timeout_seconds: int = 180
