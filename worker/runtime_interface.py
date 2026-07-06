"""Operational command surface for the worker runtime."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, Mapping

from runtime.configuration.environment import load_environment
from github.client import GitHubClient
from github.configuration import GitHubIntegrationConfig
from github.issues import IssueService
from worker.configuration import WorkerConfiguration, WorkerConfigurationLoader
from worker.daemon import WorkerDaemon
from worker.daemon.daemon import read_status
from worker.models import WorkerIssue
from worker.queue import PersistentIssueQueue


@dataclass(frozen=True, slots=True)
class RuntimeCapability:
    """Executable worker capability discovered by operational clients."""

    name: str
    method: str
    description: str
    requires_issue_number: bool = False
    requires_description: bool = False
    keywords: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CapabilityResolution:
    """Result of resolving a planned or natural-language operation to a capability."""

    requested: str
    capability: RuntimeCapability | None
    equivalent: bool
    confidence: float
    reason: str
    candidates: tuple[str, ...] = ()

    @property
    def supported(self) -> bool:
        return self.capability is not None and self.equivalent


@dataclass(slots=True)
class WorkerRuntimeInterface:
    """Thin command facade used by Discord and other operational clients."""

    loader: WorkerConfigurationLoader | None = None

    def __post_init__(self) -> None:
        load_environment()
        self.loader = self.loader or WorkerConfigurationLoader()

    def check_now(self) -> str:
        daemon = WorkerDaemon(loader=self.loader)
        daemon.initialize()
        daemon.tick()
        return self.status()

    def status(self) -> str:
        config = self._config()
        queue = PersistentIssueQueue(config.queue_persistence)
        status = read_status(config.status_path)
        latest_report = self._latest_report(config)
        return "\n".join(
            (
                "Worker status:",
                f"- Worker status: {self._running_text(status, config)}",
                f"- Queue length: {len(queue)}",
                f"- Current execution: {status.get('current_issue') or 'none'}",
                f"- Last execution: {self._last_execution(latest_report)}",
                f"- Last GitHub check: {status.get('last_poll_at') or 'never'}",
                f"- Queued issues: {', '.join(queue.keys()) if queue.keys() else 'none'}",
            )
        )

    def issues(self) -> str:
        config = self._config()
        if not config.repositories:
            return "No repository is configured for GitHub issue lookup."
        client = GitHubClient(GitHubIntegrationConfig.from_environment())
        service = IssueService(client)
        lines = ["Live GitHub issues:"]
        found = 0
        for repo in config.repositories:
            try:
                issues = service.list_open_issues(repo.owner, repo.name, limit=30)
            except Exception as exc:
                lines.append(f"- {repo.full_name}: failed to read issues ({type(exc).__name__}: {exc})")
                continue
            if not issues:
                lines.append(f"- {repo.full_name}: no open issues")
                continue
            for issue in issues:
                found += 1
                labels = f" [{', '.join(issue.labels)}]" if issue.labels else ""
                lines.append(f"- {repo.full_name}#{issue.number}: {issue.title}{labels}")
                lines.append(f"  {issue.html_url}")
        if found == 0:
            lines.append("No open GitHub issues were found in configured repositories.")
        return "\n".join(lines)

    def report(self) -> str:
        config = self._config()
        report = self._latest_report(config)
        if report is None:
            return "No engineering reports found."
        return json.dumps(report, indent=2, sort_keys=True)

    def retry_latest_failed(self) -> str:
        config = self._config()
        failed = self._latest_failed_issue(config)
        if failed is None:
            return "No failed issue found to retry."
        queue = PersistentIssueQueue(config.queue_persistence)
        issue = WorkerIssue(repository=failed["repository"], number=failed["number"], attempts=1)
        added = queue.enqueue(issue)
        return f"Retry {'queued' if added else 'already queued'}: {issue.key}"

    def retry_issue(self, issue_number: int, *, repository: object | None = None) -> str:
        config = self._config()
        repo_name = str(repository or (config.repositories[0].full_name if config.repositories else ""))
        if not repo_name:
            return "No repository is configured for issue retry."
        queue = PersistentIssueQueue(config.queue_persistence)
        issue = WorkerIssue(repository=repo_name, number=issue_number, attempts=1)
        added = queue.enqueue(issue)
        if added:
            daemon = WorkerDaemon(loader=self.loader)
            daemon.initialize()
            daemon.tick()
        return f"Retry {'queued and dispatched' if added else 'already queued'}: {issue.key}"

    def solve_issue(self, issue_number: int, *, repository: object | None = None) -> str:
        config = self._config()
        repo_name = str(repository or (config.repositories[0].full_name if config.repositories else ""))
        if not repo_name:
            return "No repository is configured for issue execution."
        queue = PersistentIssueQueue(config.queue_persistence)
        issue = WorkerIssue(repository=repo_name, number=issue_number)
        added = queue.enqueue(issue)
        if added:
            daemon = WorkerDaemon(loader=self.loader)
            daemon.initialize()
            daemon.tick()
        return f"Issue {'queued and dispatched' if added else 'already queued'}: {issue.key}"

    def create_issue(
        self,
        *,
        title: str,
        description: str,
        labels: tuple[str, ...] = (),
        repository: object | None = None,
    ) -> str:
        config = self._config()
        repo = self._repository_name(repository, config)
        if not repo:
            return "No repository is configured for GitHub issue creation."
        owner, name = repo.split("/", 1)
        clean_title = title.strip() or self._title_from_description(description)
        clean_body = self._issue_body(description)
        github_config = GitHubIntegrationConfig.from_environment()
        dry_run = not github_config.has_token
        service = IssueService(GitHubClient(github_config))
        issue = service.create_issue(owner, name, title=clean_title, body=clean_body, labels=labels, dry_run=dry_run)
        dry_run_note = " (dry run: GitHub token is not configured)" if dry_run else ""
        number = "dry-run" if issue.number == 0 else f"#{issue.number}"
        return "\n".join(
            (
                f"GitHub issue created{dry_run_note}: {repo}{number}",
                f"Title: {issue.title}",
                f"Issue URL: {issue.html_url}",
                f"Issue Number: {issue.number}",
            )
        )

    def health(self) -> str:
        daemon = WorkerDaemon(loader=self.loader)
        checks = daemon.health().startup_validation()
        lines = ["Worker health:"]
        for check in checks:
            lines.append(f"- {check.name}: {'ok' if check.healthy else 'fail'} - {check.message}")
        return "\n".join(lines)

    def pause(self) -> str:
        config = self._config()
        self._pause_path(config).write_text(json.dumps({"paused": True}, indent=2), encoding="utf-8")
        return "Scheduler paused."

    def resume(self) -> str:
        config = self._config()
        self._pause_path(config).write_text(json.dumps({"paused": False}, indent=2), encoding="utf-8")
        return "Scheduler resumed."

    def schedule(self, schedule_text: str) -> str:
        config = self._config()
        path = config.status_path.parent / "scheduler-request.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = self._schedule_payload(schedule_text, config.mode)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return f"Scheduler request recorded: {payload['summary']}"

    def help(self) -> str:
        lines = ["Available worker capabilities:"]
        for capability in self.capabilities().values():
            lines.append(f"- {capability.name}: {capability.description}")
        return "\n".join(lines)

    @classmethod
    def capabilities(cls) -> dict[str, RuntimeCapability]:
        """Return the worker command surface as the single source of truth."""

        capabilities = {
            "check_now": RuntimeCapability(
                name="check_now",
                method="check_now",
                description="Poll GitHub and run the worker immediately.",
                keywords=("check", "github", "poll", "run", "worker", "now"),
            ),
            "status": RuntimeCapability(
                name="status",
                method="status",
                description="Show worker status and queue state.",
                keywords=("status", "queue", "current", "state"),
            ),
            "issues": RuntimeCapability(
                name="issues",
                method="issues",
                description="List open GitHub issues for configured repositories.",
                keywords=("list", "open", "github", "issues", "repo"),
            ),
            "report": RuntimeCapability(
                name="report",
                method="report",
                description="Show the latest engineering report.",
                keywords=("report", "latest", "engineering", "summary"),
            ),
            "retry_latest_failed": RuntimeCapability(
                name="retry_latest_failed",
                method="retry_latest_failed",
                description="Retry the latest failed issue.",
                keywords=("retry", "failed", "latest"),
            ),
            "retry_issue": RuntimeCapability(
                name="retry_issue",
                method="retry_issue",
                description="Retry a specific GitHub issue through the worker.",
                requires_issue_number=True,
                keywords=("retry", "issue", "rerun", "again"),
            ),
            "solve_issue": RuntimeCapability(
                name="solve_issue",
                method="solve_issue",
                description="Queue and dispatch a GitHub issue through the autonomous engineering workflow.",
                requires_issue_number=True,
                keywords=("issue", "bug", "solve", "repair", "resolve", "implement", "patch", "commit", "github", "fix", "work"),
            ),
            "create_issue": RuntimeCapability(
                name="create_issue",
                method="create_issue",
                description="Create a GitHub issue in a configured repository.",
                requires_description=True,
                keywords=("create", "new", "github", "issue", "bug", "ticket"),
            ),
            "health": RuntimeCapability(
                name="health",
                method="health",
                description="Run worker health checks.",
                keywords=("health", "diagnostic", "checkup"),
            ),
            "pause": RuntimeCapability(
                name="pause",
                method="pause",
                description="Pause the worker scheduler.",
                keywords=("pause", "stop", "scheduler"),
            ),
            "resume": RuntimeCapability(
                name="resume",
                method="resume",
                description="Resume the worker scheduler.",
                keywords=("resume", "start", "scheduler"),
            ),
            "schedule": RuntimeCapability(
                name="schedule",
                method="schedule",
                description="Record a natural-language scheduler request.",
                keywords=("schedule", "recurring", "every", "interval"),
            ),
            "help": RuntimeCapability(
                name="help",
                method="help",
                description="Show available worker capabilities.",
                keywords=("help", "capabilities", "commands"),
            ),
        }
        missing = [item.method for item in capabilities.values() if not callable(getattr(cls, item.method, None))]
        if missing:
            raise RuntimeError(f"worker capability registry references missing methods: {', '.join(missing)}")
        return capabilities

    def resolve_capability(self, requested: str, *, message: str = "", inputs: Mapping[str, Any] | None = None) -> CapabilityResolution:
        text = self._resolution_text(requested, message)
        capabilities = self.capabilities()
        requested_name = self._normalize_capability_name(requested)
        if requested_name in capabilities:
            capability = capabilities[requested_name]
            return CapabilityResolution(requested, capability, True, 1.0, "exact registered capability")

        scored = sorted(
            ((self._capability_score(capability, text, inputs or {}), capability) for capability in capabilities.values()),
            key=lambda item: item[0],
            reverse=True,
        )
        best_score, best = scored[0]
        candidate_names = tuple(item.name for _, item in scored[:3])
        if best_score >= 2.0:
            return CapabilityResolution(requested, best, True, best_score, "matched registered capability from request text", candidate_names)
        return CapabilityResolution(requested, best, False, best_score, "no equivalent registered capability found", candidate_names)

    def execute_capability(self, capability: RuntimeCapability, *, inputs: Mapping[str, Any], message: str) -> str:
        if capability.requires_issue_number:
            issue_number = self._issue_number(inputs, message)
            if capability.name == "retry_issue":
                return self.retry_issue(issue_number, repository=inputs.get("repository"))
            return self.solve_issue(issue_number, repository=inputs.get("repository"))
        if capability.name == "create_issue":
            return self.create_issue(
                title=str(inputs.get("title") or ""),
                description=str(inputs.get("description") or inputs.get("body") or message),
                labels=tuple(str(label) for label in inputs.get("labels", ()) if str(label).strip()),
                repository=inputs.get("repository"),
            )
        if capability.name == "schedule":
            return self.schedule(str(inputs.get("schedule") or inputs.get("text") or inputs.get("request") or message))
        method = getattr(self, capability.method)
        return str(method())

    def is_paused(self) -> bool:
        config = self._config()
        path = self._pause_path(config)
        if not path.exists():
            return False
        return bool(json.loads(path.read_text(encoding="utf-8")).get("paused"))

    def _config(self) -> WorkerConfiguration:
        assert self.loader is not None
        _, config = self.loader.load()
        return config

    def _repository_name(self, repository: object | None, config: WorkerConfiguration) -> str:
        return str(repository or (config.repositories[0].full_name if config.repositories else ""))

    def _resolution_text(self, requested: str, message: str) -> str:
        return " ".join((requested, message)).lower().replace("_", " ").replace("-", " ")

    def _normalize_capability_name(self, requested: str) -> str:
        return re.sub(r"[^a-z0-9_]+", "_", requested.strip().lower().replace("-", "_")).strip("_")

    def _capability_score(self, capability: RuntimeCapability, text: str, inputs: Mapping[str, Any]) -> float:
        words = set(re.findall(r"[a-z0-9]+", text))
        keyword_hits = sum(1 for keyword in capability.keywords if keyword in words or keyword in text)
        score = float(keyword_hits)
        if capability.requires_issue_number and self._has_issue_number(inputs, text):
            score += 2.0
        if capability.requires_description and ("create" in words or "new" in words) and "issue" in words:
            score += 2.0
        if capability.name == "retry_latest_failed" and "retry" in words and not self._has_issue_number(inputs, text):
            score += 2.0
        if capability.name == "check_now" and "github" in words and ("check" in words or "run" in words):
            score += 2.0
        if capability.name == "status" and words & {"status", "queue"}:
            score += 2.0
        if capability.name == "health" and "health" in words:
            score += 3.0
        return score

    def _has_issue_number(self, inputs: Mapping[str, Any], text: str) -> bool:
        return bool(inputs.get("issue_number") or re.search(r"#\d+|\bissue\s+\d+\b", text, re.IGNORECASE))

    def _issue_number(self, inputs: Mapping[str, Any], message: str) -> int:
        if inputs.get("issue_number"):
            return int(inputs["issue_number"])
        match = re.search(r"#(\d+)|issue\s+(\d+)", message, re.IGNORECASE)
        if not match:
            raise ValueError("issue number is required")
        return int(next(value for value in match.groups() if value))

    def _title_from_description(self, description: str) -> str:
        first_line = next((line.strip() for line in description.splitlines() if line.strip()), "New issue")
        first_line = re.sub(r"^(bug|issue|problem|error)\s*[:\-]\s*", "", first_line, flags=re.IGNORECASE)
        if len(first_line) <= 90:
            return first_line
        return first_line[:87].rstrip() + "..."

    def _issue_body(self, description: str) -> str:
        text = description.strip()
        return "\n".join(
            (
                "## Description",
                text or "No description provided.",
                "",
                "## Acceptance Criteria",
                "- Reproduce and understand the reported behavior.",
                "- Implement the smallest safe fix.",
                "- Run relevant validation and report results.",
            )
        )

    def _schedule_payload(self, schedule_text: str, current_mode: str) -> dict[str, Any]:
        text = " ".join(schedule_text.lower().split())
        minutes: int | None = None
        if "hour" in text:
            minutes = 60
        match = re.search(r"(\d+)\s*(?:minute|min|minutes|mins)", text)
        if match:
            minutes = int(match.group(1))
        if minutes is None:
            return {"requested_schedule": schedule_text, "mode": current_mode, "summary": schedule_text or current_mode}
        return {
            "requested_schedule": schedule_text,
            "mode": "interval",
            "poll_interval_seconds": int(timedelta(minutes=minutes).total_seconds()),
            "summary": f"every {minutes} minutes",
        }

    def _pause_path(self, config: WorkerConfiguration) -> Path:
        path = config.status_path.parent / "scheduler-control.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _running_text(self, status: dict[str, Any], config: WorkerConfiguration) -> str:
        paused = self.is_paused()
        if paused:
            return "paused"
        return "running" if status.get("running") else "idle"

    def _latest_report(self, config: WorkerConfiguration) -> dict[str, Any] | None:
        directory = config.decisions.report_directory
        reports = sorted(directory.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True) if directory.exists() else []
        if not reports:
            return None
        return json.loads(reports[0].read_text(encoding="utf-8"))

    def _last_execution(self, report: dict[str, Any] | None) -> str:
        if report is None:
            return "none"
        execution_id = str(report.get("execution_id") or "unknown")
        decision = str(report.get("decision") or report.get("final_decision") or "unknown")
        return f"{execution_id} ({decision})"

    def _latest_failed_issue(self, config: WorkerConfiguration) -> dict[str, Any] | None:
        issue = self._latest_failed_issue_from_audit(config)
        if issue is not None:
            return issue
        reports = sorted(config.decisions.report_directory.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True) if config.decisions.report_directory.exists() else []
        for path in reports:
            data = json.loads(path.read_text(encoding="utf-8"))
            decision = str(data.get("decision") or data.get("final_decision") or "").lower()
            validation = str(data.get("validation") or "").lower()
            if "fail" not in decision and "retry" not in decision and "fail" not in validation:
                continue
            issue = self._issue_from_report(data)
            if issue is not None:
                return issue
        return None

    def _latest_failed_issue_from_audit(self, config: WorkerConfiguration) -> dict[str, Any] | None:
        audit_path = config.decisions.audit_directory / "audit.jsonl"
        if not audit_path.exists():
            return None
        for line in reversed(audit_path.read_text(encoding="utf-8").splitlines()):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(entry.get("result") or "").lower() != "failed":
                continue
            issue_key = str(entry.get("issue") or "")
            if "/" not in issue_key or "#" not in issue_key:
                continue
            repository, number = issue_key.rsplit("#", 1)
            return {"repository": repository, "number": int(number)}
        return None

    def _issue_from_report(self, data: dict[str, Any]) -> dict[str, Any] | None:
        issue_summary = str(data.get("issue_summary") or "")
        repository = str(data.get("repository") or "")
        if "#" in issue_summary and "/" in issue_summary:
            repo, number = issue_summary.rsplit("#", 1)
            return {"repository": repo, "number": int(number)}
        if repository and "#" in issue_summary:
            number = issue_summary.rsplit("#", 1)[1]
            return {"repository": repository, "number": int(number)}
        return None
