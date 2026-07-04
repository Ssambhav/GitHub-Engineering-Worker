"""Reusable end-to-end autonomous engineering pipeline controller."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from audit import AuditEntry, AuditLogger
from confidence import ConfidenceAssessment, ConfidenceEngine
from engineering import EngineeringExecutionPipeline
from engineering.configuration import EngineeringConfiguration
from engineering.models import EngineeringIssue, EngineeringResult
from escalation import EscalationEngine, EscalationReport
from github.client import GitHubClient
from github.configuration import GitHubIntegrationConfig
from github.pull_requests import PullRequestService
from github.workspace import RepositoryWorkspaceManager
from notifications import Notification, NotificationService, NotificationType
from reports import EngineeringReport, EngineeringReportGenerator
from runtime.models.common import utc_now
from worker.configuration import WorkerConfiguration
from worker.git_workflow import GitWorkflow, GitWorkflowResult
from worker.models import WorkerIssue, WorkerRepository


@dataclass(frozen=True, slots=True)
class PipelineControllerResult:
    issue: WorkerIssue
    status: str
    confidence: ConfidenceAssessment | None
    report: EngineeringReport | None
    escalation: EscalationReport | None
    engineering_result: EngineeringResult | None
    git_result: GitWorkflowResult | None
    attempts: int
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.status in {"completed", "pull_request_created", "dry_run_pr_created"}


@dataclass(slots=True)
class PipelineController:
    """Executes issue detection output through repository, AI, patch, tests, decision, Git, and notification."""

    config: WorkerConfiguration
    github_config: GitHubIntegrationConfig
    github_client: GitHubClient
    confidence_engine: ConfidenceEngine
    audit_logger: AuditLogger
    report_generator: EngineeringReportGenerator
    escalation_engine: EscalationEngine
    notifications: NotificationService

    def execute(self, issue: WorkerIssue, repository: WorkerRepository) -> PipelineControllerResult:
        started = time.perf_counter()
        attempts = issue.attempts
        execution_id = f"worker_{issue.repository.replace('/', '_')}_{issue.number}_{int(time.time())}"
        self._audit(execution_id, issue, "controller_started", "started", "Issue Detection")
        try:
            gh_repo = self.github_client.get_repository(repository.owner, repository.name)
            workspace = RepositoryWorkspaceManager(self.github_config)
            repo_path = workspace.clone_or_reuse(gh_repo)
            workspace.refresh(repo_path, repository.default_branch)

            pipeline = EngineeringExecutionPipeline.create(
                EngineeringConfiguration(provider=self.config.provider, model=self.config.model, workspace_root=self.config.workspace)
            )
            engineering_issue = EngineeringIssue(
                repository=issue.repository,
                number=issue.number,
                title=issue.title or f"Issue #{issue.number}",
                labels=issue.labels,
                url=issue.url,
            )
            engineering_result = pipeline.run_until_patch(
                repository_path=repo_path,
                issue=engineering_issue,
                dry_run=False,
                run_tests=self.config.decisions.run_tests,
            )
            evidence = self._evidence(execution_id, issue, repository, engineering_result, int((time.perf_counter() - started) * 1000))
            confidence = self.confidence_engine.calculate(evidence)
            report = self.report_generator.generate(evidence=evidence, confidence=confidence)
            escalation = self.escalation_engine.evaluate(issue=issue.key, repository=issue.repository, confidence=confidence, evidence=evidence)
            self._persist_report(report, escalation)

            tests_passed = all(result.passed for result in engineering_result.test_results) if engineering_result.test_results else not engineering_result.errors
            if escalation.should_escalate or not tests_passed or confidence.overall < self.config.decisions.confidence_threshold:
                self._audit(execution_id, issue, "decision", "retry_or_escalate", "Decision", confidence=confidence.overall)
                self._notify_escalation(escalation if escalation.should_escalate else self._decision_escalation(issue, confidence, evidence))
                return PipelineControllerResult(issue, "retry_or_escalate", confidence, report, escalation, engineering_result, None, attempts)

            pr_service = PullRequestService(self.github_config, self.github_client)
            git = GitWorkflow.create(self.github_config, pr_service)
            dry_run_remote = not self.github_config.has_token
            git_result = git.complete_issue(
                path=repo_path,
                owner=repository.owner,
                repo=repository.name,
                issue_number=issue.number,
                issue_title=issue.title or f"Issue #{issue.number}",
                base_branch=repository.default_branch,
                summary=self._report_summary(report),
                auto_commit=self.config.decisions.auto_commit,
                auto_push=self.config.decisions.auto_push,
                auto_create_pr=self.config.decisions.auto_create_pr,
                dry_run_remote=dry_run_remote,
                auto_cleanup=self.config.decisions.auto_cleanup,
            )
            status = "dry_run_pr_created" if git_result.dry_run else "pull_request_created"
            self._audit(execution_id, issue, "controller_completed", status, "Complete", confidence=confidence.overall)
            self._notify_success(issue, confidence, git_result)
            return PipelineControllerResult(issue, status, confidence, report, escalation, engineering_result, git_result, attempts)
        except Exception as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            evidence = {
                "execution_id": execution_id,
                "issue_summary": issue.title or issue.key,
                "repository_name": issue.repository,
                "status": "failed",
                "final_stage": "Failed",
                "retry_count": attempts,
                "failure_count": attempts + 1,
                "timeline_entries": 1,
                "artifact_count": 0,
                "unknown_failure": True,
                "execution_duration_ms": duration_ms,
            }
            confidence = self.confidence_engine.calculate(evidence)
            report = self.report_generator.generate(evidence=evidence, confidence=confidence)
            escalation = self.escalation_engine.evaluate(issue=issue.key, repository=issue.repository, confidence=confidence, evidence=evidence)
            self._persist_report(report, escalation)
            self._audit(execution_id, issue, "controller_failed", "failed", "Recovery", confidence=confidence.overall, metadata={"error": str(exc)})
            self._notify_error(issue, exc)
            return PipelineControllerResult(issue, "failed", confidence, report, escalation, None, None, attempts, error=str(exc))

    def _evidence(
        self,
        execution_id: str,
        issue: WorkerIssue,
        repository: WorkerRepository,
        result: EngineeringResult,
        duration_ms: int,
    ) -> dict[str, Any]:
        return {
            "execution_id": execution_id,
            "issue": issue,
            "issue_summary": issue.title or issue.key,
            "repository_name": repository.full_name,
            "repository": repository,
            "status": "completed" if not result.errors else "failed",
            "final_stage": "Completed" if not result.errors else "Failed",
            "timeline_entries": 10,
            "retry_count": issue.attempts,
            "artifact_count": len(result.files_modified),
            "failure_count": len(result.errors),
            "files_modified": result.files_modified,
            "files_read": (),
            "tests_executed": tuple(" ".join(command.command) for command in result.tests_executed),
            "validation": "passed" if not result.errors else "; ".join(result.errors),
            "patch_summary": result.patch_summary,
            "root_cause": "; ".join(result.engineering_notes),
            "timeline": ("issue", "repository", "analysis", "ai", "patch", "validation", "testing", "decision"),
            "execution_duration_ms": duration_ms,
            "next_recommendation": result.recommended_next_step,
        }

    def _decision_escalation(self, issue: WorkerIssue, confidence: ConfidenceAssessment, evidence: dict[str, Any]) -> EscalationReport:
        adjusted = dict(evidence)
        adjusted["unknown_failure"] = True
        return self.escalation_engine.evaluate(issue=issue.key, repository=issue.repository, confidence=confidence, evidence=adjusted)

    def _persist_report(self, report: EngineeringReport, escalation: EscalationReport) -> None:
        self.config.decisions.report_directory.mkdir(parents=True, exist_ok=True)
        path = self.config.decisions.report_directory / f"{report.execution_id}.json"
        payload = {
            "execution_id": report.execution_id,
            "issue_summary": report.issue_summary,
            "repository": report.repository,
            "validation": report.validation,
            "retries": report.retries,
            "confidence": report.confidence.overall,
            "decision": report.final_decision,
            "next_recommendation": report.next_recommendation,
            "escalation": {"should_escalate": escalation.should_escalate, "reasons": list(escalation.reasons)},
            "created_at": report.created_at.isoformat(),
        }
        path.write_text(__import__("json").dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def _audit(
        self,
        execution_id: str,
        issue: WorkerIssue,
        action: str,
        result: str,
        stage: str,
        *,
        confidence: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.audit_logger.append(
            AuditEntry(
                execution_id=execution_id,
                issue=issue.key,
                repository=issue.repository,
                current_stage=stage,
                action=action,
                result=result,
                confidence=confidence,
                retry_count=issue.attempts,
                metadata=metadata or {},
            )
        )

    def _notify_success(self, issue: WorkerIssue, confidence: ConfidenceAssessment, git_result: GitWorkflowResult) -> None:
        self.notifications.notify(
            Notification(
                NotificationType.PULL_REQUEST_CREATED,
                "Pull Request Created" if not git_result.dry_run else "Pull Request Dry Run",
                f"{issue.key} completed on branch `{git_result.branch}`.",
                repository=issue.repository,
                issue=issue.key,
                severity="success",
                fields={"confidence": confidence.overall, "commit": git_result.commit_sha or "none"},
            )
        )

    def _notify_escalation(self, escalation: EscalationReport) -> None:
        self.notifications.notify(
            Notification(
                NotificationType.ESCALATION,
                "Escalation Required",
                "; ".join(escalation.reasons) or "Decision threshold was not met.",
                repository=escalation.repository,
                issue=escalation.issue,
                severity="error",
                fields={"confidence": escalation.confidence, "recommendation": escalation.recommended_action},
            )
        )

    def _notify_error(self, issue: WorkerIssue, exc: Exception) -> None:
        self.notifications.notify(
            Notification(NotificationType.WORKER_ERROR, "Worker Error", str(exc), repository=issue.repository, issue=issue.key, severity="error")
        )

    def _report_summary(self, report: EngineeringReport) -> str:
        return (
            f"{report.patch_summary}\n\n"
            f"Validation: {report.validation}\n"
            f"Confidence: {report.confidence.overall} ({report.confidence.band})\n"
            f"Recommendation: {report.next_recommendation}"
        )
