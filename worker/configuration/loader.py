"""Load worker configuration from runtime configuration and environment."""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path
from typing import Mapping

from confidence.models import ConfidenceThresholds
from escalation.models import EscalationRules
from notifications.models import NotificationType
from runtime.configuration import RuntimeConfiguration, RuntimeConfigurationProvider
from worker.configuration.models import ScheduleMode, WorkerConfiguration, WorkerDecisionConfiguration
from worker.models import WorkerPaths, WorkerRepository


class WorkerConfigurationLoader:
    """Builds worker configuration without replacing runtime configuration."""

    def __init__(
        self,
        runtime_provider: RuntimeConfigurationProvider | None = None,
        *,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        self.runtime_provider = runtime_provider or RuntimeConfigurationProvider()
        self.environment = environment or os.environ

    def load(self) -> tuple[RuntimeConfiguration, WorkerConfiguration]:
        runtime_config = self.runtime_provider.load()
        worker_root = runtime_config.openclaw.state_dir
        paths = WorkerPaths.from_root(worker_root)
        repositories = self._repositories(runtime_config)
        interval_minutes = int(self.environment.get("WORKER_POLL_INTERVAL_MINUTES", "30"))
        cron = self.environment.get("WORKER_CRON")
        mode = self.environment.get("WORKER_MODE") or (ScheduleMode.CRON if cron else ScheduleMode.WATCH)
        worker_config = WorkerConfiguration(
            repositories=repositories,
            poll_interval=timedelta(minutes=interval_minutes),
            cron=cron,
            mode=mode,
            workspace=runtime_config.openclaw.workspace,
            default_branch=runtime_config.github.default_base_branch,
            branch_naming=runtime_config.github.branch_naming_template,
            provider=self.environment.get("WORKER_PROVIDER", "auto"),
            model=self.environment.get("WORKER_MODEL"),
            max_retries=runtime_config.execution.max_retry_attempts,
            max_concurrent_workers=runtime_config.execution.max_parallel_issues,
            queue_persistence=paths.queue_file,
            processed_issue_history=paths.processed_file,
            status_path=paths.status_file,
            decisions=self._decisions(runtime_config),
        )
        return runtime_config, worker_config

    def _decisions(self, runtime_config: RuntimeConfiguration) -> WorkerDecisionConfiguration:
        return WorkerDecisionConfiguration(
            confidence_thresholds=ConfidenceThresholds(
                auto_pr=int(self.environment.get("CONFIDENCE_AUTO_PR", "90")),
                proceed=int(self.environment.get("CONFIDENCE_PROCEED", "75")),
                retry_allowed=int(self.environment.get("CONFIDENCE_RETRY_ALLOWED", "60")),
                additional_context=int(self.environment.get("CONFIDENCE_ADDITIONAL_CONTEXT", "40")),
            ),
            audit_directory=Path(self.environment.get("WORKER_AUDIT_DIR", str(runtime_config.openclaw.audit_dir / "worker"))),
            report_directory=Path(self.environment.get("WORKER_REPORT_DIR", "reports/worker")),
            escalation_rules=EscalationRules(
                minimum_confidence=float(self.environment.get("ESCALATION_MIN_CONFIDENCE", "40")),
                max_retries=runtime_config.execution.max_retry_attempts,
                repeated_failure_limit=int(self.environment.get("ESCALATION_REPEATED_FAILURE_LIMIT", "2")),
            ),
            discord_enabled=_env_bool(self.environment.get("DISCORD_ENABLED"), default=False),
            discord_webhook=self.environment.get("DISCORD_WEBHOOK"),
            notification_types=tuple(NotificationType),
            auto_create_pr=_env_bool(self.environment.get("WORKER_AUTO_CREATE_PR"), default=True),
            auto_push=_env_bool(self.environment.get("WORKER_AUTO_PUSH"), default=True),
            auto_commit=_env_bool(self.environment.get("WORKER_AUTO_COMMIT"), default=True),
            auto_cleanup=_env_bool(self.environment.get("WORKER_AUTO_CLEANUP"), default=False),
            continue_on_failure=_env_bool(self.environment.get("WORKER_CONTINUE_ON_FAILURE"), default=True),
            confidence_threshold=float(self.environment.get("WORKER_CONFIDENCE_THRESHOLD", "75")),
            run_tests=_env_bool(self.environment.get("WORKER_RUN_TESTS"), default=True),
        )

    def _repositories(self, runtime_config: RuntimeConfiguration) -> tuple[WorkerRepository, ...]:
        configured = self.environment.get("WORKER_REPOSITORIES")
        repos: list[WorkerRepository] = []
        if configured:
            for item in configured.split(","):
                repo = _parse_repository(item.strip(), runtime_config.github.default_base_branch)
                if repo is not None:
                    repos.append(repo)
        if runtime_config.github.owner and runtime_config.github.repository:
            repos.append(
                WorkerRepository(
                    owner=runtime_config.github.owner,
                    name=runtime_config.github.repository,
                    default_branch=runtime_config.github.default_base_branch,
                )
            )
        deduped: dict[str, WorkerRepository] = {repo.full_name: repo for repo in repos}
        return tuple(deduped.values())


def _parse_repository(value: str, default_branch: str) -> WorkerRepository | None:
    if not value or "/" not in value:
        return None
    full_name, _, branch = value.partition("@")
    owner, name = full_name.split("/", 1)
    return WorkerRepository(owner=owner, name=name, default_branch=branch or default_branch)


def _env_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}
