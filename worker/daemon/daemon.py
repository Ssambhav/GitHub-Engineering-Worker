"""Autonomous worker daemon."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from audit import AuditEntry, AuditLogger
from confidence import ConfidenceAssessment, ConfidenceEngine
from discord import DiscordBotProvider, DiscordWebhookProvider
from escalation import EscalationEngine, EscalationReport
from github.client import GitHubClient
from github.configuration import GitHubIntegrationConfig
from github.issues import IssueService
from notifications import Notification, NotificationService, NotificationType
from reports import EngineeringReport, EngineeringReportGenerator
from runtime.execution import ExecutionRuntime
from runtime.configuration.environment import load_environment
from runtime.models.common import CancellationToken, IssueRef, RepositoryRef, utc_now
from worker.configuration import ScheduleMode, WorkerConfiguration, WorkerConfigurationLoader
from worker.controller import PipelineController
from worker.health import WorkerHealthMonitor
from worker.models import WorkerIssue, WorkerRepository
from worker.queue import PersistentIssueQueue
from worker.scheduler import WorkerScheduler
from worker.watcher import GitHubIssueWatcher, ProcessedIssueStore


@dataclass(slots=True)
class WorkerStatus:
    running: bool = False
    current_issue: str | None = None
    processed_count: int = 0
    queued_count: int = 0
    last_poll_at: datetime | None = None
    last_error: str | None = None
    started_at: datetime = field(default_factory=utc_now)


class WorkerDaemon:
    """Coordinates runtime startup, watching, queueing, and sequential dispatch."""

    def __init__(
        self,
        *,
        loader: WorkerConfigurationLoader | None = None,
        runtime: ExecutionRuntime | None = None,
    ) -> None:
        self.loader = loader or WorkerConfigurationLoader()
        self.runtime = runtime or ExecutionRuntime()
        self.runtime_config = None
        self.config: WorkerConfiguration | None = None
        self.queue: PersistentIssueQueue | None = None
        self.processed_store: ProcessedIssueStore | None = None
        self.watcher: GitHubIssueWatcher | None = None
        self.scheduler: WorkerScheduler | None = None
        self.confidence_engine: ConfidenceEngine | None = None
        self.audit_logger: AuditLogger | None = None
        self.report_generator: EngineeringReportGenerator | None = None
        self.escalation_engine: EscalationEngine | None = None
        self.notifications: NotificationService | None = None
        self.controller: PipelineController | None = None
        self.cancellation_token = CancellationToken()
        self.status = WorkerStatus()

    def initialize(self) -> None:
        load_environment()
        self.runtime_config, self.config = self.loader.load()
        self.runtime.configuration = self.runtime_config
        self.runtime.start()
        self.queue = PersistentIssueQueue(self.config.queue_persistence)
        self.processed_store = ProcessedIssueStore(self.config.processed_issue_history)
        github_config = GitHubIntegrationConfig.from_environment(
            token_env=self.runtime_config.github.token_env,
            workspace_path=self.runtime_config.github.workspace_path,
            branch_naming_template=self.runtime_config.github.branch_naming_template,
            commit_message_template=self.runtime_config.github.commit_message_template,
            pr_body_template=self.runtime_config.github.pr_template,
            cleanup_policy=self.runtime_config.github.cleanup_policy,
            rate_limit_threshold=self.runtime_config.github.rate_limit_threshold,
        )
        github_client = GitHubClient(github_config)
        issue_service = IssueService(github_client)
        self.watcher = GitHubIssueWatcher(
            issue_service=issue_service,
            queue=self.queue,
            processed_store=self.processed_store,
            repositories=self.config.repositories,
        )
        self.scheduler = WorkerScheduler(self.config, self.cancellation_token)
        self.confidence_engine = ConfidenceEngine(self.config.decisions.confidence_thresholds)
        self.audit_logger = AuditLogger(self.config.decisions.audit_directory)
        self.report_generator = EngineeringReportGenerator()
        self.escalation_engine = EscalationEngine(self.config.decisions.escalation_rules)
        self.notifications = NotificationService(
            providers=(
                DiscordBotProvider(
                    os.environ.get(self.config.decisions.discord_bot.token_env),
                    self.config.decisions.discord_bot,
                ),
                DiscordWebhookProvider(self.config.decisions.discord_webhook),
            ),
            enabled=self.config.decisions.discord_enabled,
            enabled_types=set(self.config.decisions.notification_types),
        )
        self.controller = PipelineController(
            config=self.config,
            github_config=github_config,
            github_client=github_client,
            confidence_engine=self.confidence_engine,
            audit_logger=self.audit_logger,
            report_generator=self.report_generator,
            escalation_engine=self.escalation_engine,
            notifications=self.notifications,
            runtime=self.runtime,
        )
        self._notify(
            Notification(
                NotificationType.WORKER_STARTED,
                "Worker Started",
                "GitHub Engineering Worker runtime started.",
                fields={"repositories": ", ".join(repo.full_name for repo in self.config.repositories)},
            )
        )
        self._write_status()

    def run(self, *, mode: str | None = None) -> WorkerStatus:
        if self.config is None:
            self.initialize()
        assert self.config is not None
        assert self.scheduler is not None
        if mode is not None:
            self.config = replace(self.config, mode=mode)
            self.scheduler = WorkerScheduler(self.config, self.cancellation_token)
        self.status.running = True
        self._write_status()
        try:
            self.scheduler.run(self.tick)
        finally:
            self.status.running = False
            self._write_status()
        return self.status

    def tick(self) -> None:
        assert self.queue is not None
        assert self.watcher is not None
        self._apply_scheduler_request()
        if self._scheduler_paused():
            self.status.queued_count = len(self.queue)
            self._write_status()
            return
        self.status.last_poll_at = utc_now()
        try:
            detected = self.watcher.poll()
            for issue in detected:
                self._notify_issue_detected(issue)
            self._drain_one()
            self.status.queued_count = len(self.queue)
            self.status.last_error = None
        except Exception as exc:
            self.status.last_error = str(exc)
            self._notify(
                Notification(
                    NotificationType.WORKER_ERROR,
                    "Worker Error",
                    str(exc),
                    severity="error",
                )
            )
            raise
        finally:
            self._write_status()

    def enqueue_issue(self, issue: WorkerIssue) -> bool:
        if self.queue is None:
            self.initialize()
        assert self.queue is not None
        added = self.queue.enqueue(issue)
        self.status.queued_count = len(self.queue)
        self._write_status()
        return added

    def health(self) -> WorkerHealthMonitor:
        if self.config is None:
            self.initialize()
        assert self.config is not None
        token_env = self.runtime_config.github.token_env if self.runtime_config else "GITHUB_TOKEN"
        return WorkerHealthMonitor(
            config=self.config,
            github_client=GitHubClient(GitHubIntegrationConfig.from_environment(token_env=token_env)),
        )

    def shutdown(self, reason: str | None = None) -> None:
        self.cancellation_token.cancel(reason or "worker shutdown requested")
        self.runtime.shutdown(reason)
        self.status.running = False
        self._write_status()

    def dispatch_issue_now(self, issue_key: str) -> Any:
        if self.queue is None:
            self.initialize()
        assert self.queue is not None
        issue = self.queue.dequeue_issue(issue_key)
        if issue is None:
            raise ValueError(f"issue is not queued: {issue_key}")
        return self._execute_queued_issue(issue)

    def _drain_one(self) -> None:
        assert self.queue is not None
        issue = self.queue.dequeue()
        if issue is None:
            return
        self._execute_queued_issue(issue)

    def _execute_queued_issue(self, issue: WorkerIssue) -> Any:
        assert self.queue is not None
        assert self.processed_store is not None
        assert self.watcher is not None
        assert self.config is not None
        self.status.current_issue = issue.key
        self.watcher.mark_in_progress(issue.key)
        self._write_status()
        try:
            result = self._execute_issue(issue)
            if result.succeeded:
                self.processed_store.mark_processed(issue.key, status=result.status)
                self.status.processed_count += 1
            elif self._should_retry_issue(result.status, attempts=issue.attempts):
                self.queue.retry_enqueue(issue)
                self._notify(
                    Notification(
                        NotificationType.RETRY_STARTED,
                        "Retry Started",
                        f"Retrying {issue.key}.",
                        repository=issue.repository,
                        issue=issue.key,
                        severity="warning",
                        fields={"attempt": issue.attempts + 1},
                    )
                )
            else:
                self.processed_store.mark_processed(issue.key, status=result.status)
            return result
        except Exception as exc:
            self._audit(
                issue,
                action="issue_failed",
                result="failed",
                current_stage="worker_dispatch",
                retry_count=issue.attempts,
                metadata={"error": str(exc)},
            )
            if self.config and issue.attempts < self.config.max_retries:
                self.queue.retry_enqueue(issue)
                self._notify(
                    Notification(
                        NotificationType.RETRY_STARTED,
                        "Retry Started",
                        f"Retrying {issue.key}.",
                        repository=issue.repository,
                        issue=issue.key,
                        severity="warning",
                        fields={"attempt": issue.attempts + 1},
                    )
                )
            else:
                self._notify(
                    Notification(
                        NotificationType.RETRY_FAILED,
                        "Retry Failed",
                        f"Retry budget exhausted for {issue.key}.",
                        repository=issue.repository,
                        issue=issue.key,
                        severity="error",
                    )
                )
            if not self.config.decisions.continue_on_failure:
                raise
            raise
        finally:
            self.watcher.clear_in_progress(issue.key)
            self.status.current_issue = None

    def _should_retry_issue(self, status: str, *, attempts: int) -> bool:
        if attempts >= self.config.max_retries:
            return False
        return status not in {"retry_or_escalate", "escalated"}

    def _execute_issue(self, issue: WorkerIssue) -> Any:
        assert self.config is not None
        if self.controller is not None:
            repository = next((item for item in self.config.repositories if item.full_name == issue.repository), None)
            if repository is None:
                owner, name = issue.repository.split("/", 1)
                repository = WorkerRepository(owner=owner, name=name, default_branch=self.config.default_branch)
            return self.controller.execute(issue, repository)
        summary = self._dispatch(issue)
        return type("LegacyControllerResult", (), {"succeeded": summary.status == "completed", "status": summary.status})()

    def _dispatch(self, issue: WorkerIssue) -> Any:
        owner, repo = issue.repository.split("/", 1)
        repository = next((item for item in self.config.repositories if item.full_name == issue.repository), None) if self.config else None
        repo_ref = RepositoryRef(
            provider="github",
            owner=owner,
            name=repo,
            default_branch=repository.default_branch if repository else "main",
        )
        issue_ref = IssueRef(provider="github", repository=issue.repository, issue_number=issue.number, title=issue.title, url=issue.url)
        return self.runtime.run_workflow(issue=issue_ref, repository=repo_ref)

    def _evidence(self, issue: WorkerIssue, summary: Any, *, duration_ms: int) -> dict[str, Any]:
        return {
            "execution_id": str(summary.execution_id),
            "issue": IssueRef(provider="github", repository=issue.repository, issue_number=issue.number, title=issue.title, url=issue.url),
            "issue_summary": issue.title or issue.key,
            "repository_name": issue.repository,
            "repository": RepositoryRef(provider="github", owner=issue.repository.split("/", 1)[0], name=issue.repository.split("/", 1)[1]),
            "final_stage": str(summary.final_stage),
            "status": str(summary.status),
            "timeline_entries": int(summary.timeline_entries),
            "retry_count": int(summary.retry_count),
            "artifact_count": len(summary.artifact_refs),
            "failure_count": 0 if summary.status == "completed" else 1,
            "timeline": tuple(summary.visited_states),
            "files_modified": (),
            "files_read": (),
            "tests_executed": (),
            "validation": summary.status,
            "execution_duration_ms": duration_ms,
            "next_recommendation": "complete" if summary.status == "completed" else "review",
        }

    def _confidence(self, evidence: dict[str, Any]) -> ConfidenceAssessment:
        assert self.confidence_engine is not None
        return self.confidence_engine.calculate(evidence)

    def _report(self, evidence: dict[str, Any], confidence: ConfidenceAssessment) -> EngineeringReport:
        assert self.report_generator is not None
        return self.report_generator.generate(evidence=evidence, confidence=confidence)

    def _escalation(self, issue: WorkerIssue, confidence: ConfidenceAssessment, evidence: dict[str, Any]) -> EscalationReport:
        assert self.escalation_engine is not None
        return self.escalation_engine.evaluate(issue=issue.key, repository=issue.repository, confidence=confidence, evidence=evidence)

    def _persist_report(self, report: EngineeringReport, escalation: EscalationReport) -> None:
        assert self.config is not None
        self.config.decisions.report_directory.mkdir(parents=True, exist_ok=True)
        path = self.config.decisions.report_directory / f"{_safe_name(report.execution_id)}.json"
        payload = {
            "execution_id": report.execution_id,
            "issue_summary": report.issue_summary,
            "repository": report.repository,
            "root_cause": report.root_cause,
            "files_read": list(report.files_read),
            "files_modified": list(report.files_modified),
            "prompt_summary": report.prompt_summary,
            "patch_summary": report.patch_summary,
            "validation": report.validation,
            "tests": list(report.tests),
            "retries": report.retries,
            "confidence": {
                "overall": report.confidence.overall,
                "band": report.confidence.band,
                "decision_recommendation": report.confidence.decision_recommendation,
                "per_stage": [
                    {"stage": item.stage, "score": item.score, "rationale": item.rationale, "weight": item.weight}
                    for item in report.confidence.per_stage
                ],
            },
            "timeline": list(report.timeline),
            "final_decision": report.final_decision,
            "next_recommendation": report.next_recommendation,
            "escalation": {
                "should_escalate": escalation.should_escalate,
                "reasons": list(escalation.reasons),
                "recommended_action": escalation.recommended_action,
            },
            "created_at": report.created_at.isoformat(),
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def _audit(
        self,
        issue: WorkerIssue,
        *,
        action: str,
        result: str,
        current_stage: str,
        execution_id: str = "unknown",
        decision: str | None = None,
        confidence: float | None = None,
        retry_count: int = 0,
        files_modified: tuple[str, ...] = (),
        tests_executed: tuple[str, ...] = (),
        execution_duration_ms: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if self.audit_logger is None:
            return
        self.audit_logger.append(
            AuditEntry(
                execution_id=execution_id,
                issue=issue.key,
                repository=issue.repository,
                current_stage=current_stage,
                current_agent=None,
                current_tool=None,
                action=action,
                decision=decision,
                confidence=confidence,
                retry_count=retry_count,
                files_modified=files_modified,
                tests_executed=tests_executed,
                execution_duration_ms=execution_duration_ms,
                result=result,
                metadata=metadata or {},
            )
        )

    def _notify(self, notification: Notification) -> None:
        if self.notifications is None:
            return
        self.notifications.notify(notification)

    def _notify_issue_detected(self, issue: WorkerIssue) -> None:
        self._notify(
            Notification(
                NotificationType.ISSUE_DETECTED,
                "Issue Detected",
                f"Queued {issue.key}.",
                repository=issue.repository,
                issue=issue.key,
                fields={"title": issue.title or ""},
            )
        )

    def _notify_issue_solved(self, issue: WorkerIssue, confidence: ConfidenceAssessment) -> None:
        self._notify(
            Notification(
                NotificationType.ISSUE_SOLVED,
                "Issue Solved",
                f"Completed {issue.key}.",
                repository=issue.repository,
                issue=issue.key,
                severity="success",
                fields={"confidence": confidence.overall, "decision": confidence.decision_recommendation},
            )
        )

    def _notify_escalation(self, escalation: EscalationReport) -> None:
        self._notify(
            Notification(
                NotificationType.ESCALATION,
                "Escalation Required",
                "; ".join(escalation.reasons),
                repository=escalation.repository,
                issue=escalation.issue,
                severity="error",
                fields={"confidence": escalation.confidence, "recommendation": escalation.recommended_action},
            )
        )

    def _write_status(self) -> None:
        if self.config is None:
            return
        self.config.status_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "running": self.status.running,
            "current_issue": self.status.current_issue,
            "processed_count": self.status.processed_count,
            "queued_count": self.status.queued_count,
            "last_poll_at": self.status.last_poll_at.isoformat() if self.status.last_poll_at else None,
            "last_error": self.status.last_error,
            "started_at": self.status.started_at.isoformat(),
        }
        self.config.status_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def _scheduler_paused(self) -> bool:
        if self.config is None:
            return False
        path = self.config.status_path.parent / "scheduler-control.json"
        if not path.exists():
            return False
        try:
            return bool(json.loads(path.read_text(encoding="utf-8")).get("paused"))
        except json.JSONDecodeError:
            return False

    def _apply_scheduler_request(self) -> None:
        if self.config is None:
            return
        path = self.config.status_path.parent / "scheduler-request.json"
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return
        mode = str(data.get("mode") or self.config.mode)
        interval_seconds = data.get("poll_interval_seconds")
        poll_interval = self.config.poll_interval
        if interval_seconds is not None:
            poll_interval = timedelta(seconds=max(1, int(interval_seconds)))
        cron = data.get("cron")
        self.config = replace(self.config, mode=mode, poll_interval=poll_interval, cron=cron)
        self.scheduler = WorkerScheduler(self.config, self.cancellation_token)


def read_status(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"running": False, "message": "worker has not written status yet"}
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value)
