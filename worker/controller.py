"""Reusable end-to-end autonomous engineering pipeline controller."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from audit import AuditEntry, AuditLogger
from confidence import ConfidenceAssessment, ConfidenceEngine
from engineering import EngineeringExecutionPipeline
from engineering.configuration import EngineeringConfiguration
from engineering.models import EngineeringIssue, EngineeringResult, TestResult
from escalation import EscalationEngine, EscalationReport
from github.branches import BranchService
from github.client import GitHubClient
from github.configuration import GitHubIntegrationConfig
from github.pull_requests import PullRequestService
from github.repositories import RepositoryOperations
from github.workspace import RepositoryWorkspaceManager
from notifications import Notification, NotificationService, NotificationType
from reports import EngineeringReport, EngineeringReportGenerator, StageTimelineEntry
from runtime.execution import ExecutionRuntime
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
    runtime: ExecutionRuntime | None = None

    def execute(self, issue: WorkerIssue, repository: WorkerRepository) -> PipelineControllerResult:
        started = time.perf_counter()
        attempts = issue.attempts
        execution_id = f"worker_{issue.repository.replace('/', '_')}_{issue.number}_{int(time.time())}"
        stage_timeline: list[StageTimelineEntry] = []
        self._audit(execution_id, issue, "controller_started", "started", "Issue Detection")
        try:
            self._record_queue_stage(issue, stage_timeline)
            gh_repo = self._run_stage(
                stage_timeline,
                "Workspace",
                lambda: self.github_client.get_repository(repository.owner, repository.name),
            )
            workspace = RepositoryWorkspaceManager(self.github_config)
            repo_path = self._run_stage(stage_timeline, "Repository checkout", lambda: workspace.clone_or_reuse(gh_repo))
            self._run_stage(stage_timeline, "Repository checkout", lambda: workspace.refresh(repo_path, repository.default_branch), returned_value=repo_path)
            branch_service = BranchService(self.github_config, RepositoryOperations())
            self._run_stage(
                stage_timeline,
                "Branch creation",
                lambda: branch_service.create_issue_branch(
                    repo_path,
                    issue_number=issue.number,
                    title=issue.title or f"Issue #{issue.number}",
                    base=repository.default_branch,
                ),
            )
            original_body = str(issue.metadata.get("body", ""))
            engineering_result = None
            attempt_count = 0
            while attempt_count <= self.config.max_retries:
                attempt_count += 1
                engineering_issue = EngineeringIssue(
                    repository=issue.repository,
                    number=issue.number,
                    title=issue.title or f"Issue #{issue.number}",
                    body=original_body,
                    labels=issue.labels,
                    url=issue.url,
                )
                pipeline = EngineeringExecutionPipeline.create(
                    EngineeringConfiguration(
                        model=self.config.model,
                        openclaw_cli=self.config.openclaw_cli,
                        openclaw_agent_id=self.config.openclaw_agent_id,
                        openclaw_agent_mode=self.config.openclaw_agent_mode,
                        openclaw_agent_fallback_enabled=self.config.openclaw_agent_fallback_enabled,
                        openclaw_timeout_seconds=self.config.openclaw_timeout_seconds,
                        openclaw_retries=self.config.openclaw_retries,
                        openclaw_thinking=self.config.openclaw_thinking,
                        workspace_root=self.config.workspace,
                    )
                )
                engineering_result = self._run_stage(
                    stage_timeline,
                    "OpenClaw Agent launch",
                    lambda: pipeline.run_until_patch(
                        repository_path=repo_path,
                        issue=engineering_issue,
                        dry_run=self._runtime_dry_run(),
                        run_tests=self.config.decisions.run_tests,
                    ),
                )
                self._record_agent_completion_stage(stage_timeline, engineering_result)
                if engineering_result.files_modified:
                    break
                if attempt_count <= self.config.max_retries:
                    self._audit(
                        execution_id,
                        issue,
                        "engineering_retry",
                        "no_repository_changes",
                        "Engineering",
                        metadata={"attempt": attempt_count, "reason": self._result_failure_note(engineering_result)},
                    )
                    continue
                break
            assert engineering_result is not None
            evidence = self._evidence(
                execution_id,
                issue,
                repository,
                engineering_result,
                int((time.perf_counter() - started) * 1000),
                stage_timeline,
            )
            confidence = self.confidence_engine.calculate(evidence)
            report = self.report_generator.generate(evidence=evidence, confidence=confidence)
            escalation = self.escalation_engine.evaluate(issue=issue.key, repository=issue.repository, confidence=confidence, evidence=evidence)
            self._persist_report(report, escalation, evidence)

            if not engineering_result.files_modified:
                decision_evidence = dict(evidence)
                decision_evidence["failure_reason"] = self._result_failure_note(engineering_result)
                report_escalation = self.escalation_engine.evaluate(
                    issue=issue.key,
                    repository=issue.repository,
                    confidence=confidence,
                    evidence=decision_evidence,
                )
                self._audit(execution_id, issue, "decision", "escalated", "Decision", confidence=confidence.overall)
                self._run_stage(stage_timeline, "Discord notification", lambda: self._notify_escalation(report_escalation))
                self._run_stage(stage_timeline, "Repository checkout", lambda: workspace.refresh(repo_path, repository.default_branch), returned_value=repo_path)
                report = self.report_generator.generate(evidence={**evidence, "execution_timeline": tuple(stage_timeline)}, confidence=confidence)
                self._persist_report(report, escalation, {**evidence, "execution_timeline": tuple(stage_timeline)})
                return PipelineControllerResult(issue, "escalated", confidence, report, report_escalation, engineering_result, None, attempt_count)

            pr_service = PullRequestService(self.github_config, self.github_client)
            git = GitWorkflow.create(self.github_config, pr_service)
            dry_run_remote = self._runtime_dry_run() or not self.github_config.has_token
            self._run_stage(stage_timeline, "Repository changes detection", lambda: self._detect_repository_changes(engineering_result))
            git_result = self._complete_git_workflow(
                stage_timeline=stage_timeline,
                git=git,
                repo_path=repo_path,
                repository=repository,
                issue=issue,
                report=report,
                dry_run_remote=dry_run_remote,
            )
            status = "dry_run_pr_created" if git_result.dry_run else "pull_request_created"
            self._audit(execution_id, issue, "controller_completed", status, "Complete", confidence=confidence.overall)
            self._run_stage(stage_timeline, "Discord notification", lambda: self._notify_success(issue, confidence, git_result))
            report = self.report_generator.generate(evidence={**evidence, "execution_timeline": tuple(stage_timeline)}, confidence=confidence)
            self._persist_report(report, escalation, {**evidence, "execution_timeline": tuple(stage_timeline)})
            return PipelineControllerResult(issue, status, confidence, report, escalation, engineering_result, git_result, attempt_count)
        except Exception as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            self._ensure_failure_stage(stage_timeline, exc)
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
                "failure_reason": f"controller exception: {exc.__class__.__name__}: {exc}",
                "execution_duration_ms": duration_ms,
                "execution_timeline": tuple(stage_timeline),
            }
            confidence = self.confidence_engine.calculate(evidence)
            report = self.report_generator.generate(evidence=evidence, confidence=confidence)
            escalation = self.escalation_engine.evaluate(issue=issue.key, repository=issue.repository, confidence=confidence, evidence=evidence)
            self._persist_report(report, escalation, evidence)
            self._audit(execution_id, issue, "controller_failed", "failed", "Recovery", confidence=confidence.overall, metadata={"error": str(exc)})
            try:
                self._run_stage(stage_timeline, "Discord notification", lambda: self._notify_error(issue, exc))
            except Exception:
                pass
            report = self.report_generator.generate(evidence={**evidence, "execution_timeline": tuple(stage_timeline)}, confidence=confidence)
            self._persist_report(report, escalation, {**evidence, "execution_timeline": tuple(stage_timeline)})
            return PipelineControllerResult(issue, "failed", confidence, report, escalation, None, None, attempts, error=str(exc))

    def _runtime_dry_run(self) -> bool:
        runtime_config = self.runtime.configuration if self.runtime is not None else None
        execution = getattr(runtime_config, "execution", None)
        return bool(getattr(execution, "dry_run", False))

    def _evidence(
        self,
        execution_id: str,
        issue: WorkerIssue,
        repository: WorkerRepository,
        result: EngineeringResult,
        duration_ms: int,
        stage_timeline: tuple[StageTimelineEntry, ...] | list[StageTimelineEntry],
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
            "validation": self._validation_summary(result),
            "patch_summary": result.patch_summary,
            "root_cause": "; ".join(result.engineering_notes),
            "timeline": ("issue", "repository", "analysis", "ai", "patch", "validation", "testing", "decision"),
            "execution_timeline": tuple(stage_timeline),
            "execution_duration_ms": duration_ms,
            "next_recommendation": result.recommended_next_step,
            "verification_steps": self._verification_steps(result),
            "browser_actions": self._browser_actions(result),
            "screenshots": tuple(result.verification.screenshot_paths) if result.verification else (),
            "why_fixed": result.patch_summary,
            "execution_mode": result.execution_metadata.mode if result.execution_metadata else "unknown",
            "execution_model": result.execution_metadata.selected_model if result.execution_metadata else None,
            "execution_provider": result.execution_metadata.selected_provider if result.execution_metadata else None,
            "execution_command": tuple(result.execution_metadata.command) if result.execution_metadata else (),
            "execution_subprocess": tuple(result.execution_metadata.subprocess) if result.execution_metadata else (),
            "execution_reason": result.execution_metadata.selected_reason if result.execution_metadata else "unknown",
            "execution_fallback_reason": result.execution_metadata.fallback_reason if result.execution_metadata else None,
        }

    def _persist_report(self, report: EngineeringReport, escalation: EscalationReport, evidence: dict[str, Any]) -> None:
        self.config.decisions.report_directory.mkdir(parents=True, exist_ok=True)
        path = self.config.decisions.report_directory / f"{report.execution_id}.json"
        execution_timeline = tuple(evidence.get("execution_timeline", report.execution_timeline))
        payload = {
            "execution_id": report.execution_id,
            "issue_summary": report.issue_summary,
            "repository": report.repository,
            "validation": report.validation,
            "verification_steps": list(report.verification_steps),
            "browser_actions": list(report.browser_actions),
            "screenshots": list(report.screenshots),
            "why_fixed": report.why_fixed,
            "tests": list(report.tests),
            "retries": report.retries,
            "confidence": report.confidence.overall,
            "decision": report.final_decision,
            "next_recommendation": report.next_recommendation,
            "execution_mode": evidence.get("execution_mode"),
            "execution_model": evidence.get("execution_model"),
            "execution_provider": evidence.get("execution_provider"),
            "execution_command": list(evidence.get("execution_command", ())),
            "execution_subprocess": list(evidence.get("execution_subprocess", ())),
            "execution_reason": evidence.get("execution_reason"),
            "execution_fallback_reason": evidence.get("execution_fallback_reason"),
            "execution_timeline": [
                {
                    "stage_name": entry.stage_name,
                    "status": entry.status,
                    "start_time": entry.start_time.isoformat(),
                    "end_time": entry.end_time.isoformat(),
                    "exception": entry.exception,
                    "exit_code": entry.exit_code,
                    "stderr": entry.stderr,
                    "stdout": entry.stdout,
                    "returned_value": entry.returned_value,
                }
                for entry in execution_timeline
            ],
            "escalation": {"should_escalate": escalation.should_escalate, "reasons": list(escalation.reasons)},
            "created_at": report.created_at.isoformat(),
        }
        path.write_text(__import__("json").dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def _record_queue_stage(self, issue: WorkerIssue, stage_timeline: list[StageTimelineEntry]) -> None:
        stage_timeline.append(
            StageTimelineEntry(
                stage_name="Queue",
                status="PASS",
                start_time=issue.enqueued_at,
                end_time=utc_now(),
                exception=None,
                exit_code=0,
                stderr="",
                stdout="",
                returned_value=issue.key,
            )
        )

    def _run_stage(
        self,
        stage_timeline: list[StageTimelineEntry],
        stage_name: str,
        action: Any,
        *,
        returned_value: Any = None,
    ) -> Any:
        start_time = utc_now()
        try:
            value = action()
        except Exception as exc:
            stage_timeline.append(
                StageTimelineEntry(
                    stage_name=stage_name,
                    status="FAIL",
                    start_time=start_time,
                    end_time=utc_now(),
                    exception=f"{exc.__class__.__name__}: {exc}",
                    exit_code=getattr(exc, "exit_code", 1),
                    stderr=str(getattr(exc, "stderr", "") or ""),
                    stdout=str(getattr(exc, "stdout", "") or ""),
                    returned_value=str(getattr(exc, "returned_value", "") or ""),
                )
            )
            raise
        stage_timeline.append(
            StageTimelineEntry(
                stage_name=stage_name,
                status="PASS",
                start_time=start_time,
                end_time=utc_now(),
                exception=None,
                exit_code=0,
                stderr="",
                stdout="",
                returned_value=self._stringify_value(value if returned_value is None else returned_value),
            )
        )
        return value

    def _record_agent_completion_stage(self, stage_timeline: list[StageTimelineEntry], result: EngineeringResult) -> None:
        metadata = result.execution_metadata
        now = utc_now()
        if metadata is None:
            stage_timeline.append(
                StageTimelineEntry(
                    stage_name="OpenClaw Agent completion",
                    status="PASS",
                    start_time=now,
                    end_time=now,
                    exception=None,
                    exit_code=0,
                    stderr="",
                    stdout="",
                    returned_value=self._stringify_value(result.patch_summary),
                )
            )
            return
        failed = bool(metadata.stage_exception or metadata.fallback_reason)
        stage_timeline.append(
            StageTimelineEntry(
                stage_name="OpenClaw Agent completion",
                status="FAIL" if failed else "PASS",
                start_time=now,
                end_time=now,
                exception=metadata.stage_exception or metadata.fallback_reason,
                exit_code=metadata.stage_exit_code if metadata.stage_exit_code is not None else (1 if failed else 0),
                stderr=metadata.stage_stderr,
                stdout=metadata.stage_stdout,
                returned_value=metadata.stage_returned_value or self._stringify_value(result.patch_summary),
            )
        )

    def _detect_repository_changes(self, engineering_result: EngineeringResult) -> tuple[str, ...]:
        return engineering_result.files_modified

    def _complete_git_workflow(
        self,
        *,
        stage_timeline: list[StageTimelineEntry],
        git: GitWorkflow,
        repo_path: Path,
        repository: WorkerRepository,
        issue: WorkerIssue,
        report: EngineeringReport,
        dry_run_remote: bool,
    ) -> GitWorkflowResult:
        current_branch = self._run_stage(stage_timeline, "Commit", lambda: git.operations.current_branch(repo_path))
        branch = current_branch
        if current_branch == repository.default_branch:
            branch = self._run_stage(
                stage_timeline,
                "Branch creation",
                lambda: git.branch_service.create_issue_branch(
                    repo_path,
                    issue_number=issue.number,
                    title=issue.title or f"Issue #{issue.number}",
                    base=repository.default_branch,
                ),
            )
        if branch == repository.default_branch:
            raise ValueError("refusing to commit directly to the default branch")

        changed = self._run_stage(stage_timeline, "Repository changes detection", lambda: git.operations.changed_files(repo_path))
        commit_sha = None
        if self.config.decisions.auto_commit and changed:
            commit_sha = self._run_stage(
                stage_timeline,
                "Commit",
                lambda: git.commit_service.create_commit(
                    repo_path,
                    issue_number=issue.number,
                    title=issue.title or f"Issue #{issue.number}",
                    files=changed,
                ),
            )

        pushed = False
        if self.config.decisions.auto_push and commit_sha:
            self._run_stage(stage_timeline, "Push", lambda: git.operations.push_branch(repo_path, branch, dry_run=dry_run_remote))
            pushed = True

        pull_request = None
        if self.config.decisions.auto_create_pr and (commit_sha or dry_run_remote):
            pull_request = self._run_stage(
                stage_timeline,
                "Pull Request",
                lambda: git.pull_request_service.create_pr(
                    repository.owner,
                    repository.name,
                    issue_number=issue.number,
                    issue_title=issue.title or f"Issue #{issue.number}",
                    summary=self._report_summary(report),
                    head=branch,
                    base=repository.default_branch,
                    dry_run=dry_run_remote,
                ),
            )

        if self.config.decisions.auto_cleanup and dry_run_remote and branch != repository.default_branch:
            self._run_stage(stage_timeline, "Repository checkout", lambda: git.operations.checkout_branch(repo_path, repository.default_branch))
            self._run_stage(stage_timeline, "Branch creation", lambda: git.operations.delete_branch(repo_path, branch, force=True), returned_value=branch)

        return GitWorkflowResult(branch=branch, commit_sha=commit_sha, pushed=pushed, pull_request=pull_request, dry_run=dry_run_remote)

    def _ensure_failure_stage(self, stage_timeline: list[StageTimelineEntry], exc: Exception) -> None:
        if stage_timeline and stage_timeline[-1].status == "FAIL":
            return
        now = utc_now()
        stage_timeline.append(
            StageTimelineEntry(
                stage_name="Controller",
                status="FAIL",
                start_time=now,
                end_time=now,
                exception=f"{exc.__class__.__name__}: {exc}",
                exit_code=getattr(exc, "exit_code", 1),
                stderr=str(getattr(exc, "stderr", "") or ""),
                stdout=str(getattr(exc, "stdout", "") or ""),
                returned_value=str(getattr(exc, "returned_value", "") or ""),
            )
        )

    def _stringify_value(self, value: Any) -> str:
        if value is None:
            return "null"
        if isinstance(value, (str, int, float, bool)):
            return str(value)
        if isinstance(value, Path):
            return str(value)
        try:
            return __import__("json").dumps(value, default=self._json_default, sort_keys=True)
        except (TypeError, ValueError):
            return repr(value)

    def _json_default(self, value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Path):
            return str(value)
        if hasattr(value, "__dataclass_fields__"):
            return asdict(value)
        return repr(value)

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
                fields={
                    "issue": issue.key,
                    "confidence": confidence.overall,
                    "files_changed": "see engineering report",
                    "tests": "see engineering report",
                    "commit": git_result.commit_sha or "none",
                    "branch": git_result.branch,
                    "pr_url": git_result.pull_request.html_url if git_result.pull_request and git_result.pull_request.html_url else "none",
                    "execution_time": "see engineering report",
                    "ai_summary": "Worker completed the autonomous engineering pipeline.",
                },
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
            f"Why fixed: {report.why_fixed}\n"
            f"Confidence: {report.confidence.overall} ({report.confidence.band})\n"
            f"Recommendation: {report.next_recommendation}"
        )

    def _result_failure_note(self, result: EngineeringResult) -> str:
        if result.files_modified:
            return ""
        errors = list(result.errors)
        return "; ".join(errors) or "OpenClaw Agent could not determine a fix or produced no repository changes"

    def _format_test_failure(self, result: TestResult) -> str:
        return f"test failed: {' '.join(result.command)} (exit {result.exit_code})"

    def _validation_summary(self, result: EngineeringResult) -> str:
        parts: list[str] = []
        if result.errors:
            parts.append("; ".join(result.errors))
        if result.test_results:
            if all(item.passed for item in result.test_results):
                parts.append("tests passed")
            else:
                parts.extend(self._format_test_failure(item) for item in result.test_results if not item.passed)
        return "; ".join(parts) if parts else "not run"

    def _verification_steps(self, result: EngineeringResult) -> tuple[str, ...]:
        if result.verification is None:
            return ()
        steps = [
            f"Open application at {result.verification.target_url or 'unknown URL'}",
            "Wait for page to finish loading",
            "Read page title and visible text",
            "Capture screenshot",
            "Evaluate acceptance criteria against browser evidence",
        ]
        return tuple(steps)

    def _browser_actions(self, result: EngineeringResult) -> tuple[str, ...]:
        if result.verification is None:
            return ()
        return tuple(
            f"{action.action}: {'success' if action.success else 'failed'}"
            + (f" ({action.url})" if action.url else "")
            for action in result.verification.actions
        )

    def _decision_failure_reasons(
        self,
        *,
        engineering_result: EngineeringResult,
        tests_passed: bool,
        verification_passed: bool,
        confidence: ConfidenceAssessment,
    ) -> tuple[str, ...]:
        reasons: list[str] = []
        if engineering_result.errors:
            reasons.extend(str(error) for error in engineering_result.errors if str(error).strip())
        if not tests_passed:
            reasons.extend(self._format_test_failure(item) for item in engineering_result.test_results if not item.passed)
        if engineering_result.verification is not None and not verification_passed:
            reasons.append(engineering_result.verification.summary)
        if confidence.overall < self.config.decisions.confidence_threshold:
            reasons.append(
                f"confidence {confidence.overall:.2f} below threshold {self.config.decisions.confidence_threshold:.2f}"
            )
        if not reasons:
            reasons.append("execution ended without a successful validation decision")
        return tuple(reasons)
