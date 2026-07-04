"""Configuration models for the autonomous worker runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

from confidence.models import ConfidenceThresholds
from escalation.models import EscalationRules
from notifications.models import NotificationType
from worker.models import WorkerRepository


class ScheduleMode:
    """Supported scheduler modes."""

    INTERVAL = "interval"
    CRON = "cron"
    MANUAL = "manual"
    ONCE = "once"
    WATCH = "watch"


@dataclass(frozen=True, slots=True)
class WorkerDecisionConfiguration:
    """Decision-making, audit, report, escalation, and notification settings."""

    confidence_thresholds: ConfidenceThresholds = field(default_factory=ConfidenceThresholds)
    audit_directory: Path = Path("audit/worker")
    report_directory: Path = Path("reports/worker")
    escalation_rules: EscalationRules = field(default_factory=EscalationRules)
    discord_enabled: bool = False
    discord_webhook: str | None = None
    notification_types: tuple[NotificationType, ...] = tuple(NotificationType)
    auto_create_pr: bool = True
    auto_push: bool = True
    auto_commit: bool = True
    auto_cleanup: bool = False
    continue_on_failure: bool = True
    confidence_threshold: float = 75.0
    run_tests: bool = True


@dataclass(frozen=True, slots=True)
class WorkerConfiguration:
    """Worker-specific configuration derived from runtime settings."""

    repositories: tuple[WorkerRepository, ...] = ()
    poll_interval: timedelta = timedelta(minutes=30)
    cron: str | None = None
    mode: str = ScheduleMode.WATCH
    workspace: Path = Path(".")
    default_branch: str = "main"
    branch_naming: str = "gew/issue-{issue_number}-{slug}"
    provider: str = "auto"
    model: str | None = None
    max_retries: int = 3
    max_concurrent_workers: int = 1
    queue_persistence: Path = Path("states/worker/queue.json")
    processed_issue_history: Path = Path("states/worker/processed-issues.json")
    status_path: Path = Path("states/worker/status.json")
    decisions: WorkerDecisionConfiguration = field(default_factory=WorkerDecisionConfiguration)

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not self.repositories:
            errors.append("at least one repository must be configured")
        if self.poll_interval.total_seconds() <= 0:
            errors.append("poll interval must be greater than zero")
        if self.max_retries < 0:
            errors.append("max retries cannot be negative")
        if self.max_concurrent_workers < 1:
            errors.append("max concurrent workers must be at least 1")
        if self.mode not in {ScheduleMode.INTERVAL, ScheduleMode.CRON, ScheduleMode.MANUAL, ScheduleMode.ONCE, ScheduleMode.WATCH}:
            errors.append(f"unsupported schedule mode: {self.mode}")
        if self.mode == ScheduleMode.CRON and not self.cron:
            errors.append("cron mode requires a cron expression")
        return tuple(errors)
