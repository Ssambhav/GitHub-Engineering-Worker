"""Configuration for search, context, providers, patches, and tests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class EngineeringConfiguration:
    """Strongly typed engineering execution settings."""

    provider: str = "auto"
    model: str | None = None
    openclaw_cli: str = "openclaw"
    openclaw_agent_id: str = "main"
    openclaw_agent_mode: str = "agent"
    openclaw_agent_fallback_enabled: bool = True
    openclaw_timeout_seconds: int = 180
    openclaw_retries: int = 1
    openclaw_thinking: str | None = None
    openai_api_key_env: str = "OPENAI_API_KEY"
    openrouter_api_key_env: str = "OPENROUTER_API_KEY"
    min_candidate_files: int = 4
    max_candidate_files: int = 12
    max_files_to_read: int = 6
    max_file_bytes: int = 8_000
    max_context_bytes: int = 30_000
    min_search_passes: int = 3
    min_root_cause_evidence: int = 2
    max_patch_changed_files: int = 24
    max_patch_changed_lines: int = 2_000
    max_patch_repair_attempts: int = 2
    workspace_root: Path = Path(".")
    test_timeout_seconds: int = 180
