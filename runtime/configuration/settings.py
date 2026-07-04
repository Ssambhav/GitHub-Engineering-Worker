"""Typed runtime configuration models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from runtime.models.common import immutable_mapping


@dataclass(frozen=True, slots=True)
class ProjectSettings:
    name: str = "GitHub Engineering Worker"
    mode: str = "autonomous-engineering-worker"
    environment: str = "development"


@dataclass(frozen=True, slots=True)
class OpenClawSettings:
    workspace: Path = Path(".")
    runtime_dir: Path = Path("runtime")
    state_dir: Path = Path("states")
    memory_dir: Path = Path("memory")
    audit_dir: Path = Path("audit")


@dataclass(frozen=True, slots=True)
class GitHubSettings:
    owner: str | None = None
    repository: str | None = None
    token_env: str = "GITHUB_TOKEN"
    default_base_branch: str = "main"
    branch_prefix: str = "gew/"


@dataclass(frozen=True, slots=True)
class ExecutionSettings:
    dry_run: bool = True
    require_human_approval_for: tuple[str, ...] = ()
    max_parallel_issues: int = 1
    max_retry_attempts: int = 3


@dataclass(frozen=True, slots=True)
class ObservabilitySettings:
    log_level: str = "info"
    audit_decisions: bool = True
    retain_runtime_artifacts: bool = False


@dataclass(frozen=True, slots=True)
class RuntimeConfiguration:
    """Root runtime configuration."""

    project: ProjectSettings = field(default_factory=ProjectSettings)
    openclaw: OpenClawSettings = field(default_factory=OpenClawSettings)
    github: GitHubSettings = field(default_factory=GitHubSettings)
    execution: ExecutionSettings = field(default_factory=ExecutionSettings)
    observability: ObservabilitySettings = field(default_factory=ObservabilitySettings)
    policies: Mapping[str, str] = field(default_factory=immutable_mapping)

