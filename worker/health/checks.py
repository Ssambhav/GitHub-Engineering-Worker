"""Health monitoring for worker startup and runtime state."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from github.client import GitHubClient
from worker.configuration import WorkerConfiguration


@dataclass(frozen=True, slots=True)
class HealthCheckResult:
    name: str
    healthy: bool
    message: str


class WorkerHealthMonitor:
    """Runs validation and connectivity checks without mutating repositories."""

    def __init__(self, *, config: WorkerConfiguration, github_client: GitHubClient | None = None) -> None:
        self.config = config
        self.github_client = github_client

    def startup_validation(self) -> tuple[HealthCheckResult, ...]:
        return (
            self.configuration_validation(),
            self.workspace_validation(),
            self.github_connectivity_check(),
            self.provider_availability_check(),
        )

    def configuration_validation(self) -> HealthCheckResult:
        errors = self.config.validate()
        return HealthCheckResult("configuration", not errors, "; ".join(errors) if errors else "configuration is valid")

    def workspace_validation(self) -> HealthCheckResult:
        workspace = Path(self.config.workspace)
        return HealthCheckResult("workspace", workspace.exists(), f"workspace exists: {workspace}" if workspace.exists() else f"workspace missing: {workspace}")

    def github_connectivity_check(self) -> HealthCheckResult:
        if self.github_client is None:
            return HealthCheckResult("github", False, "GitHub client is not configured")
        try:
            ok = self.github_client.validate_credentials()
        except Exception as exc:
            return HealthCheckResult("github", False, str(exc))
        return HealthCheckResult("github", ok, "GitHub credentials are valid" if ok else "GitHub token is not configured")

    def provider_availability_check(self) -> HealthCheckResult:
        provider = self.config.provider
        if provider == "auto":
            return HealthCheckResult("provider", True, "provider auto-selection enabled")
        return HealthCheckResult("provider", True, f"provider configured: {provider}")

    def summary(self) -> str:
        checks = self.startup_validation()
        status = "healthy" if all(check.healthy for check in checks) else "unhealthy"
        details = ", ".join(f"{check.name}={check.healthy}" for check in checks)
        return f"{status}: {details}"
