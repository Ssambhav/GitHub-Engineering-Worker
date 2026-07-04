"""Configuration loading and validation."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Mapping

from runtime.configuration.settings import (
    ExecutionSettings,
    GitHubSettings,
    ObservabilitySettings,
    OpenClawSettings,
    ProjectSettings,
    RuntimeConfiguration,
)
from runtime.exceptions import ConfigurationException
from runtime.models.common import immutable_mapping

_ENV_PATTERN = re.compile(r"^\$\{(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?::-(?P<default>.*))?}$")


class RuntimeConfigurationProvider:
    """Loads runtime configuration from defaults, YAML files, and env vars.

    The parser supports the simple YAML subset used by this repository's
    configuration file: nested mappings, scalar values, booleans, integers, and
    list items. This keeps the runtime stdlib-only while remaining compatible
    with future providers that may use PyYAML or another backend.
    """

    def __init__(
        self,
        config_path: Path | str = Path("configuration/settings.yaml"),
        *,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        self.config_path = Path(config_path)
        self.environment = environment or os.environ

    def load(self) -> RuntimeConfiguration:
        data = self._load_file() if self.config_path.exists() else {}
        resolved = self._resolve_env(data)
        config = self._to_configuration(resolved)
        self._validate(config)
        return config

    def _load_file(self) -> dict[str, Any]:
        try:
            return _parse_simple_yaml(self.config_path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ConfigurationException(
                f"Unable to read runtime configuration: {self.config_path}",
                details={"path": str(self.config_path), "error": str(exc)},
            ) from exc

    def _resolve_env(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self._resolve_env(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._resolve_env(item) for item in value]
        if isinstance(value, str):
            match = _ENV_PATTERN.match(value)
            if match:
                name = match.group("name")
                default = match.group("default")
                return self.environment.get(name, default)
        return value

    def _to_configuration(self, data: Mapping[str, Any]) -> RuntimeConfiguration:
        project = data.get("project", {})
        openclaw = data.get("openclaw", {})
        github = data.get("github", {})
        execution = data.get("execution", {})
        observability = data.get("observability", {})
        policies = data.get("policies", {})

        return RuntimeConfiguration(
            project=ProjectSettings(
                name=str(project.get("name", "GitHub Engineering Worker")),
                mode=str(project.get("mode", "autonomous-engineering-worker")),
                environment=str(project.get("environment", "development")),
            ),
            openclaw=OpenClawSettings(
                workspace=Path(str(openclaw.get("workspace", "."))),
                runtime_dir=Path(str(openclaw.get("runtime_dir", "runtime"))),
                state_dir=Path(str(openclaw.get("state_dir", "states"))),
                memory_dir=Path(str(openclaw.get("memory_dir", "memory"))),
                audit_dir=Path(str(openclaw.get("audit_dir", "audit"))),
            ),
            github=GitHubSettings(
                owner=_optional_str(github.get("owner")),
                repository=_optional_str(github.get("repository")),
                token_env=str(github.get("token_env", "GITHUB_TOKEN")),
                workspace_path=Path(str(github.get("workspace_path", ".workspaces"))),
                branch_naming_template=str(github.get("branch_naming_template", "gew/issue-{issue_number}-{slug}")),
                commit_message_template=str(github.get("commit_message_template", "Fix issue #{issue_number}: {title}")),
                pr_template=str(github.get("pr_template", "{summary}\n\nCloses #{issue_number}")),
                cleanup_policy=str(github.get("cleanup_policy", "keep")),
                rate_limit_threshold=int(github.get("rate_limit_threshold", 25)),
                default_base_branch=str(github.get("default_base_branch", "main")),
                branch_prefix=str(github.get("branch_prefix", "gew/")),
            ),
            execution=ExecutionSettings(
                dry_run=bool(execution.get("dry_run", True)),
                require_human_approval_for=tuple(execution.get("require_human_approval_for", ())),
                max_parallel_issues=int(execution.get("max_parallel_issues", 1)),
                max_retry_attempts=int(execution.get("max_retry_attempts", 3)),
            ),
            observability=ObservabilitySettings(
                log_level=str(observability.get("log_level", "info")),
                audit_decisions=bool(observability.get("audit_decisions", True)),
                retain_runtime_artifacts=bool(observability.get("retain_runtime_artifacts", False)),
            ),
            policies=immutable_mapping({str(key): str(val) for key, val in dict(policies).items()}),
        )

    def _validate(self, config: RuntimeConfiguration) -> None:
        if config.execution.max_parallel_issues < 1:
            raise ConfigurationException("max_parallel_issues must be at least 1")
        if config.execution.max_retry_attempts < 0:
            raise ConfigurationException("max_retry_attempts cannot be negative")
        if not config.github.token_env:
            raise ConfigurationException("github.token_env must be configured")
        if config.github.rate_limit_threshold < 0:
            raise ConfigurationException("github.rate_limit_threshold cannot be negative")


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, root)]
    pending_key: tuple[int, dict[str, Any], str] | None = None

    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()

        if stripped.startswith("- "):
            if pending_key is None:
                raise ConfigurationException("List item without parent key", details={"line": raw_line})
            parent_indent, parent, key = pending_key
            if indent <= parent_indent:
                raise ConfigurationException("Invalid list indentation", details={"line": raw_line})
            current = parent.get(key)
            if current is None or isinstance(current, dict) and not current:
                current = []
                parent[key] = current
            if not isinstance(current, list):
                raise ConfigurationException("Mixed mapping/list YAML is unsupported", details={"line": raw_line})
            current.append(_parse_scalar(stripped[2:].strip()))
            continue

        while stack and indent <= stack[-1][0]:
            stack.pop()
        if not stack:
            raise ConfigurationException("Invalid YAML indentation", details={"line": raw_line})

        if ":" not in stripped:
            raise ConfigurationException("Invalid YAML line", details={"line": raw_line})

        key, raw_value = stripped.split(":", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        parent = stack[-1][1]
        if not isinstance(parent, dict):
            raise ConfigurationException("Cannot assign mapping under list", details={"line": raw_line})

        if raw_value == "":
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
            pending_key = (indent, parent, key)
        else:
            parent[key] = _parse_scalar(raw_value)
            pending_key = None

    return root


def _parse_scalar(value: str) -> Any:
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if value.lower() in {"null", "none", "~"}:
        return None
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        return value
