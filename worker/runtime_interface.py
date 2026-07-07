"""Unified runtime capability registry and execution facade."""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Any, Mapping

from decision.engine import JsonlDecisionMemory
from engineering.providers.openclaw import OpenClawProvider, OpenClawProviderError
from github.client import GitHubClient
from github.configuration import GitHubIntegrationConfig
from github.issues import IssueService
from github.workspace import RepositoryWorkspaceManager
from runtime.configuration.environment import load_environment
from runtime.execution import ExecutionRuntime
from runtime.models.common import IssueRef, RepositoryRef
from tools.context import ToolRequest
from worker.configuration import WorkerConfiguration, WorkerConfigurationLoader
from worker.daemon import WorkerDaemon
from worker.daemon.daemon import read_status
from worker.models import WorkerIssue
from worker.queue import PersistentIssueQueue
from worker.watcher import ProcessedIssueStore


@dataclass(frozen=True, slots=True)
class RuntimeCapability:
    """Executable capability discovered from the shared runtime."""

    name: str
    description: str
    source: str
    method: str | None = None
    tool_id: str | None = None
    tool_capability: str | None = None
    requires_issue_number: bool = False
    requires_description: bool = False
    keywords: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def slash_name(self) -> str:
        name = self.name.replace(".", "-").replace("_", "-")
        return re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")[:32]


@dataclass(frozen=True, slots=True)
class CapabilityResolution:
    """Result of resolving a request to a registered capability."""

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
    """Shared capability discovery and execution facade for operational clients."""

    loader: WorkerConfigurationLoader | None = None
    runtime: ExecutionRuntime = field(default_factory=ExecutionRuntime)
    memory: JsonlDecisionMemory | None = None

    def __post_init__(self) -> None:
        load_environment()
        self.loader = self.loader or WorkerConfigurationLoader()
        self.runtime.start()
        _, config = self.loader.load()
        self.memory = self.memory or JsonlDecisionMemory(config.decisions.audit_directory / "runtime-interface-memory.jsonl")

    def check_now(self) -> str:
        daemon = WorkerDaemon(loader=self.loader, runtime=self.runtime)
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
                f"- Worker status: {self._running_text(status)}",
                f"- Queue length: {len(queue)}",
                f"- Current execution: {status.get('current_issue') or 'none'}",
                f"- Last execution: {self._last_execution(latest_report)}",
                f"- Last GitHub check: {status.get('last_poll_at') or 'never'}",
                f"- Queued issues: {', '.join(queue.keys()) if queue.keys() else 'none'}",
            )
        )

    def queue(self) -> str:
        config = self._config()
        queue = PersistentIssueQueue(config.queue_persistence)
        keys = queue.keys()
        if not keys:
            return "Worker queue is empty."
        return "\n".join(("Queued issues:", *(f"- {key}" for key in keys)))

    def clear_queue(self) -> str:
        config = self._config()
        queue = PersistentIssueQueue(config.queue_persistence)
        cleared = queue.clear()
        status = read_status(config.status_path)
        lines = ["Cleared pending queue."]
        lines.append(f"Removed: {len(cleared)}")
        lines.append(f"Running job: {status.get('current_issue') or 'unchanged'}")
        lines.append("Suggested action: use `stop current task` if you also want to halt the active execution.")
        return "\n".join(lines)

    def remove_issue(self, issue_number: int, *, repository: object | None = None) -> str:
        issue_key = self._issue_key(issue_number, repository=repository)
        queue = PersistentIssueQueue(self._config().queue_persistence)
        removed = queue.dequeue_issue(issue_key)
        if removed is None:
            return self._failure_response(
                stage="queue removal",
                reason=f"{issue_key} is not waiting in the pending queue.",
                suggested_action="Use `show queue` or `show current job` to see where the issue is currently tracked.",
            )
        return "\n".join((f"Removed {issue_key} from queue.", f"Queue size: {len(queue)}"))

    def cancel_issue(self, issue_number: int, *, repository: object | None = None) -> str:
        issue_key = self._issue_key(issue_number, repository=repository)
        config = self._config()
        queue = PersistentIssueQueue(config.queue_persistence)
        if queue.dequeue_issue(issue_key) is not None:
            return "\n".join((f"Cancelled {issue_key}.", f"Stage: queue removal", "Reason: pending issue removed before execution."))
        status = read_status(config.status_path)
        current_issue = str(status.get("current_issue") or "")
        if current_issue == issue_key:
            return self.stop_current_job(issue_number=issue_number, repository=repository)
        return self._failure_response(
            stage="issue cancellation",
            reason=f"{issue_key} is neither queued nor running.",
            suggested_action="Use `show queue` or `show current job` to confirm the current worker state.",
        )

    def restart_issue(self, issue_number: int, *, repository: object | None = None) -> str:
        issue_key = self._issue_key(issue_number, repository=repository)
        config = self._config()
        queue = PersistentIssueQueue(config.queue_persistence)
        queue.dequeue_issue(issue_key)
        self._clear_retry_state(issue_key, config=config)
        self._clear_history(issue_key, config=config)
        self._clear_workspace(issue_key, config=config)
        self._clear_reports(issue_key, config=config)
        issue = self._load_worker_issue(issue_number, repository=repository, attempts=0)
        queue.enqueue(issue)
        daemon = WorkerDaemon(loader=self.loader, runtime=self.runtime)
        daemon.initialize()
        result = daemon.dispatch_issue_now(issue.key)
        return "\n".join(
            (
                "Previous execution cleared.",
                "Workspace reset.",
                "Retry history cleared.",
                f"Issue requeued: {issue.key}.",
                f"Worker started: {result.status}.",
            )
        )

    def run_issue_now(self, issue_number: int, *, repository: object | None = None) -> str:
        config = self._config()
        repo_name = self._repository_name(repository, config)
        if not repo_name:
            return self._failure_response(
                stage="issue dispatch",
                reason="No repository is configured for issue execution.",
                suggested_action="Configure at least one repository before dispatching GitHub issues.",
            )
        queue = PersistentIssueQueue(config.queue_persistence)
        issue = self._load_worker_issue(issue_number, repository=repository, attempts=0)
        if not queue.contains(issue.key):
            queue.enqueue(issue)
        else:
            queue.move_to_front(issue.key)
        daemon = WorkerDaemon(loader=self.loader, runtime=self.runtime)
        daemon.initialize()
        result = daemon.dispatch_issue_now(issue.key)
        return "\n".join((f"Worker started on {issue.key}.", f"Dispatch result: {result.status}."))

    def prioritize_issue(self, issue_number: int, *, repository: object | None = None) -> str:
        issue_key = self._issue_key(issue_number, repository=repository)
        queue = PersistentIssueQueue(self._config().queue_persistence)
        moved = queue.move_to_front(issue_key)
        if moved is None:
            return self._failure_response(
                stage="queue prioritization",
                reason=f"{issue_key} is not in the pending queue.",
                suggested_action=f"Use `run issue #{issue_number} now` to enqueue and dispatch it immediately.",
            )
        return "\n".join((f"Moved {issue_key} to the front of the queue.", f"Queue size: {len(queue)}"))

    def move_issue_to_front(self, issue_number: int, *, repository: object | None = None) -> str:
        return self.prioritize_issue(issue_number, repository=repository)

    def list_queue(self) -> str:
        return self.queue()

    def show_current_job(self) -> str:
        config = self._config()
        status = read_status(config.status_path)
        current_issue = status.get("current_issue")
        if not current_issue:
            return "Current job: none."
        return "\n".join(
            (
                f"Current job: {current_issue}",
                f"Worker status: {self._running_text(status)}",
                f"Last poll: {status.get('last_poll_at') or 'never'}",
            )
        )

    def show_worker_state(self) -> str:
        return self.status()

    def stop_current_job(self, issue_number: int | None = None, *, repository: object | None = None) -> str:
        config = self._config()
        status = read_status(config.status_path)
        current_issue = str(status.get("current_issue") or "")
        if issue_number is not None:
            requested_issue = self._issue_key(issue_number, repository=repository)
            if current_issue and current_issue != requested_issue:
                return self._failure_response(
                    stage="job cancellation",
                    reason=f"{requested_issue} is not the active job.",
                    suggested_action=f"Use `cancel issue {issue_number}` only when that issue is running, or remove it from the queue instead.",
                )
        if not current_issue:
            return self._failure_response(
                stage="job cancellation",
                reason="No active job is running.",
                suggested_action="Use `run issue #<n> now` to start a job immediately.",
            )
        self.pause()
        stop_path = config.status_path.parent / "current-job-control.json"
        stop_path.parent.mkdir(parents=True, exist_ok=True)
        stop_path.write_text(json.dumps({"cancel_requested": True, "issue": current_issue}, indent=2, sort_keys=True), encoding="utf-8")
        return "\n".join(
            (
                f"Stop requested for {current_issue}.",
                "Stage: runtime cancellation",
                "Reason: active worker job was asked to halt.",
                "Suggested action: use `continue working` after the workspace is ready for another dispatch.",
            )
        )

    def resume_current_job(self) -> str:
        config = self._config()
        control_path = config.status_path.parent / "current-job-control.json"
        if control_path.exists():
            control_path.unlink()
        self.resume()
        status = read_status(config.status_path)
        current_issue = status.get("current_issue")
        if current_issue:
            return f"Worker resumed. Active job remains {current_issue}."
        return "Worker resumed."

    def clear_retry_state(self, issue_number: int, *, repository: object | None = None) -> str:
        issue_key = self._issue_key(issue_number, repository=repository)
        changed = self._clear_retry_state(issue_key, config=self._config())
        if changed:
            return f"Retry state cleared for {issue_key}."
        return self._failure_response(
            stage="retry reset",
            reason=f"No stored retry state was found for {issue_key}.",
            suggested_action="Use `restart issue #<n>` if you want a full fresh run with workspace and report cleanup.",
        )

    def clear_history(self, issue_number: int, *, repository: object | None = None) -> str:
        issue_key = self._issue_key(issue_number, repository=repository)
        changed = self._clear_history(issue_key, config=self._config())
        if changed:
            return f"Execution history cleared for {issue_key}."
        return self._failure_response(
            stage="history reset",
            reason=f"No persisted execution history was found for {issue_key}.",
            suggested_action="Use `show queue` or `show current job` to confirm whether the issue still exists in runtime state.",
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
        issue = self._load_worker_issue(failed["number"], repository=failed["repository"], attempts=1)
        added = queue.enqueue(issue)
        return f"Retry {'queued' if added else 'already queued'}: {issue.key}"

    def retry_issue(self, issue_number: int, *, repository: object | None = None) -> str:
        config = self._config()
        repo_name = self._repository_name(repository, config)
        if not repo_name:
            return "No repository is configured for issue retry."
        queue = PersistentIssueQueue(config.queue_persistence)
        issue = self._load_worker_issue(issue_number, repository=repository, attempts=1)
        added = queue.enqueue(issue)
        if added:
            daemon = WorkerDaemon(loader=self.loader, runtime=self.runtime)
            daemon.initialize()
            result = daemon.dispatch_issue_now(issue.key)
            return f"Retry queued and executed: {issue.key} ({result.status})"
        return f"Retry already queued: {issue.key}"

    def solve_issue(self, issue_number: int, *, repository: object | None = None) -> str:
        config = self._config()
        repo_name = self._repository_name(repository, config)
        if not repo_name:
            return "No repository is configured for issue execution."
        queue = PersistentIssueQueue(config.queue_persistence)
        issue = self._load_worker_issue(issue_number, repository=repository, attempts=0)
        added = queue.enqueue(issue)
        if added:
            daemon = WorkerDaemon(loader=self.loader, runtime=self.runtime)
            daemon.initialize()
            result = daemon.dispatch_issue_now(issue.key)
            return f"Issue queued and executed: {issue.key} ({result.status})"
        return f"Issue already queued: {issue.key}"

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
        daemon = WorkerDaemon(loader=self.loader, runtime=self.runtime)
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

    def memory_remember(self, *, key: str, value: Any) -> str:
        assert self.memory is not None
        self.memory.propose_update(key, {"value": value})
        return f"Stored memory: {key}"

    def memory_show(self, *, key: str) -> str:
        assert self.memory is not None
        value = self.memory.read(key)
        return json.dumps({"key": key, "value": value}, indent=2, sort_keys=True, default=str)

    def memory_forget(self, *, key: str) -> str:
        assert self.memory is not None
        self.memory.propose_update(key, {"forgotten": True})
        return f"Forgot memory: {key}"

    def help(self) -> str:
        lines = ["Available runtime capabilities:"]
        for capability in self.capabilities().values():
            lines.append(f"- {capability.name}: {capability.description}")
        return "\n".join(lines)

    def capabilities(self) -> dict[str, RuntimeCapability]:
        capabilities = {capability.name: capability for capability in self._operational_capabilities()}
        for capability in self._tool_capabilities():
            capabilities.setdefault(capability.name, capability)
        return capabilities

    def slash_commands(self) -> tuple[dict[str, str], ...]:
        commands: list[dict[str, str]] = []
        seen: set[str] = set()
        for capability in self.capabilities().values():
            if not capability.slash_name or capability.slash_name in seen:
                continue
            seen.add(capability.slash_name)
            commands.append({"name": capability.slash_name, "description": capability.description[:100] or capability.name})
        return tuple(commands)

    def resolve_capability(self, requested: str, *, message: str = "", inputs: Mapping[str, Any] | None = None) -> CapabilityResolution:
        text = self._resolution_text(requested, message)
        requested_name = self._normalize_capability_name(requested)
        capabilities = self.capabilities()
        if requested_name in capabilities:
            capability = capabilities[requested_name]
            return CapabilityResolution(requested, capability, True, 1.0, "exact registered capability")
        by_alias = {alias: capability for capability in capabilities.values() for alias in capability.aliases}
        if requested_name in by_alias:
            capability = by_alias[requested_name]
            return CapabilityResolution(requested, capability, True, 0.95, "matched registered capability alias")

        scored = sorted(
            ((self._capability_score(capability, text, inputs or {}), capability) for capability in capabilities.values()),
            key=lambda item: item[0],
            reverse=True,
        )
        best_score, best = scored[0]
        candidates = tuple(item.name for _, item in scored[:5])
        if best_score >= 2.0:
            return CapabilityResolution(requested, best, True, best_score, "matched registered capability from request text", candidates)
        return CapabilityResolution(requested, best, False, best_score, "no equivalent registered capability found", candidates)

    def execute_capability(self, capability: RuntimeCapability, *, inputs: Mapping[str, Any], message: str) -> str:
        if capability.source == "operation":
            return self._execute_operational_capability(capability, inputs=inputs, message=message)
        if capability.source == "tool":
            return self._execute_tool_capability(capability, inputs=inputs, message=message)
        raise ValueError(f"unsupported runtime capability source: {capability.source}")

    def startup_diagnostics(self) -> dict[str, Any]:
        config = self._config()
        github_config = GitHubIntegrationConfig.from_environment()
        openclaw = OpenClawProvider()
        openclaw_status = openclaw.health()
        try:
            model_selection = openclaw.model_selection()
        except OpenClawProviderError:
            model_selection = None
        return {
            "worker_version": self._worker_version(),
            "git_commit": self._git_commit(),
            "pid": os.getpid(),
            "repository": [repo.full_name for repo in config.repositories] or [str(config.workspace)],
            "loaded_capabilities": sorted(self.capabilities().keys()),
            "github_status": "configured" if github_config.has_token else "token_missing",
            "discord_status": "configured" if bool(os.environ.get(config.decisions.discord_bot.token_env)) else "token_missing",
            "openclaw_status": {
                "installed": openclaw_status.installed,
                "callable": openclaw_status.callable,
                "configured": openclaw_status.configured,
                "reason": openclaw_status.reason,
                "selected_provider": openclaw_status.selected_provider,
                "default_model": model_selection.default_model if model_selection else None,
                "resolved_model": model_selection.resolved_model if model_selection else None,
            },
            "scheduler_status": "paused" if self.is_paused() else "active",
            "browser_status": "registered" if any(name.startswith("browser.") for name in self.capabilities()) else "unavailable",
        }

    def is_paused(self) -> bool:
        config = self._config()
        path = self._pause_path(config)
        if not path.exists():
            return False
        return bool(json.loads(path.read_text(encoding="utf-8")).get("paused"))

    def _execute_operational_capability(self, capability: RuntimeCapability, *, inputs: Mapping[str, Any], message: str) -> str:
        if capability.requires_issue_number:
            issue_number = self._issue_number(inputs, message)
            if capability.name == "retry_issue":
                return self.retry_issue(issue_number, repository=inputs.get("repository"))
            if capability.name == "remove_issue":
                return self.remove_issue(issue_number, repository=inputs.get("repository"))
            if capability.name == "cancel_issue":
                return self.cancel_issue(issue_number, repository=inputs.get("repository"))
            if capability.name == "restart_issue":
                return self.restart_issue(issue_number, repository=inputs.get("repository"))
            if capability.name == "run_issue_now":
                return self.run_issue_now(issue_number, repository=inputs.get("repository"))
            if capability.name == "prioritize_issue":
                return self.prioritize_issue(issue_number, repository=inputs.get("repository"))
            if capability.name == "move_issue_to_front":
                return self.move_issue_to_front(issue_number, repository=inputs.get("repository"))
            if capability.name == "clear_retry_state":
                return self.clear_retry_state(issue_number, repository=inputs.get("repository"))
            if capability.name == "clear_history":
                return self.clear_history(issue_number, repository=inputs.get("repository"))
            if capability.name == "stop_current_job":
                return self.stop_current_job(issue_number=issue_number, repository=inputs.get("repository"))
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
        if capability.name == "memory.remember":
            return self.memory_remember(key=str(inputs.get("key") or "discord:user"), value=inputs.get("value") or message)
        if capability.name == "memory.show":
            return self.memory_show(key=str(inputs.get("key") or "discord:user"))
        if capability.name == "memory.forget":
            return self.memory_forget(key=str(inputs.get("key") or "discord:user"))
        method = getattr(self, capability.method or "")
        return str(method())

    def _execute_tool_capability(self, capability: RuntimeCapability, *, inputs: Mapping[str, Any], message: str) -> str:
        request_inputs = self._tool_inputs(capability, inputs, message)
        request = ToolRequest(
            tool_id=str(capability.tool_id),
            capability=capability.tool_capability,
            inputs=request_inputs,
        )
        context = self._tool_context()
        assert self.runtime.tool_executor is not None
        result = self.runtime.tool_executor.execute(request, self.runtime.tool_executor.create_context(context, request))
        payload = {
            "success": result.success,
            "status": result.status.value,
            "tool_id": capability.tool_id,
            "capability": capability.tool_capability,
            "output": dict(result.structured_output),
            "errors": list(result.errors),
            "warnings": list(result.warnings),
        }
        return json.dumps(payload, indent=2, sort_keys=True, default=str)

    def _operational_capabilities(self) -> tuple[RuntimeCapability, ...]:
        operations = (
            RuntimeCapability(
                name="check_now",
                method="check_now",
                description="Poll GitHub and run the worker immediately.",
                source="operation",
                keywords=("check", "github", "poll", "run", "worker", "now"),
                aliases=("run_worker",),
            ),
            RuntimeCapability(
                name="status",
                method="status",
                description="Show worker status and queue state.",
                source="operation",
                keywords=("status", "queue", "current", "state"),
            ),
            RuntimeCapability(
                name="queue",
                method="queue",
                description="Show queued issues waiting for execution.",
                source="operation",
                keywords=("queue", "queued", "backlog"),
                aliases=("show_queue",),
            ),
            RuntimeCapability(
                name="clear_queue",
                method="clear_queue",
                description="Remove every pending issue from the queue without touching the active job.",
                source="operation",
                keywords=("clear", "empty", "queue", "pending"),
                aliases=("empty_queue",),
            ),
            RuntimeCapability(
                name="list_queue",
                method="list_queue",
                description="List the current pending queue.",
                source="operation",
                keywords=("list", "show", "queue"),
            ),
            RuntimeCapability(
                name="issues",
                method="issues",
                description="List open GitHub issues for configured repositories.",
                source="operation",
                keywords=("list", "open", "github", "issues", "repo"),
            ),
            RuntimeCapability(
                name="report",
                method="report",
                description="Show the latest engineering report.",
                source="operation",
                keywords=("report", "latest", "engineering", "summary"),
            ),
            RuntimeCapability(
                name="retry_latest_failed",
                method="retry_latest_failed",
                description="Retry the latest failed issue.",
                source="operation",
                keywords=("retry", "failed", "latest"),
            ),
            RuntimeCapability(
                name="retry_issue",
                method="retry_issue",
                description="Retry a specific GitHub issue through the worker runtime.",
                source="operation",
                requires_issue_number=True,
                keywords=("retry", "issue", "rerun", "again"),
            ),
            RuntimeCapability(
                name="remove_issue",
                method="remove_issue",
                description="Remove a pending issue from the worker queue.",
                source="operation",
                requires_issue_number=True,
                keywords=("remove", "delete", "drop", "queue", "issue"),
            ),
            RuntimeCapability(
                name="cancel_issue",
                method="cancel_issue",
                description="Cancel a queued or active issue execution.",
                source="operation",
                requires_issue_number=True,
                keywords=("cancel", "stop", "issue", "task"),
            ),
            RuntimeCapability(
                name="restart_issue",
                method="restart_issue",
                description="Clear previous execution state, requeue the issue fresh, and dispatch it immediately.",
                source="operation",
                requires_issue_number=True,
                keywords=("restart", "reset", "fresh", "issue"),
            ),
            RuntimeCapability(
                name="run_issue_now",
                method="run_issue_now",
                description="Dispatch a specific issue immediately, bypassing FIFO order.",
                source="operation",
                requires_issue_number=True,
                keywords=("run", "issue", "now", "immediately"),
            ),
            RuntimeCapability(
                name="prioritize_issue",
                method="prioritize_issue",
                description="Move a queued issue to the front of the queue.",
                source="operation",
                requires_issue_number=True,
                keywords=("prioritize", "priority", "front", "queue", "issue"),
            ),
            RuntimeCapability(
                name="move_issue_to_front",
                method="move_issue_to_front",
                description="Move a queued issue to the front of the queue.",
                source="operation",
                requires_issue_number=True,
                keywords=("move", "front", "queue", "issue"),
            ),
            RuntimeCapability(
                name="solve_issue",
                method="solve_issue",
                description="Queue and dispatch a GitHub issue through the autonomous engineering workflow.",
                source="operation",
                requires_issue_number=True,
                keywords=("issue", "bug", "solve", "repair", "resolve", "implement", "patch", "commit", "github", "fix", "work"),
            ),
            RuntimeCapability(
                name="create_issue",
                method="create_issue",
                description="Create a GitHub issue in a configured repository.",
                source="operation",
                requires_description=True,
                keywords=("create", "new", "github", "issue", "bug", "ticket"),
            ),
            RuntimeCapability(
                name="health",
                method="health",
                description="Run worker health checks.",
                source="operation",
                keywords=("health", "diagnostic", "checkup"),
            ),
            RuntimeCapability(
                name="show_current_job",
                method="show_current_job",
                description="Show the issue the worker is actively executing.",
                source="operation",
                keywords=("current", "job", "doing", "working", "active"),
            ),
            RuntimeCapability(
                name="show_worker_state",
                method="show_worker_state",
                description="Show the current worker state, queue length, and execution details.",
                source="operation",
                keywords=("worker", "state", "status"),
            ),
            RuntimeCapability(
                name="stop_current_job",
                method="stop_current_job",
                description="Request cancellation of the active job and pause new dispatches.",
                source="operation",
                keywords=("stop", "current", "job", "task", "halt"),
            ),
            RuntimeCapability(
                name="resume_current_job",
                method="resume_current_job",
                description="Resume the worker after a stop or pause request.",
                source="operation",
                keywords=("resume", "continue", "working", "job"),
            ),
            RuntimeCapability(
                name="pause",
                method="pause",
                description="Pause the worker scheduler.",
                source="operation",
                keywords=("pause", "stop", "scheduler"),
            ),
            RuntimeCapability(
                name="resume",
                method="resume",
                description="Resume the worker scheduler.",
                source="operation",
                keywords=("resume", "start", "scheduler"),
            ),
            RuntimeCapability(
                name="schedule",
                method="schedule",
                description="Record a natural-language scheduler request.",
                source="operation",
                keywords=("schedule", "recurring", "every", "interval"),
            ),
            RuntimeCapability(
                name="clear_retry_state",
                method="clear_retry_state",
                description="Clear stored retry metadata for a specific issue.",
                source="operation",
                requires_issue_number=True,
                keywords=("clear", "retry", "state", "reset", "issue"),
            ),
            RuntimeCapability(
                name="clear_history",
                method="clear_history",
                description="Clear stored processed-history state for a specific issue.",
                source="operation",
                requires_issue_number=True,
                keywords=("clear", "history", "forget", "issue", "attempt"),
            ),
            RuntimeCapability(
                name="memory.remember",
                description="Store a runtime memory value.",
                source="operation",
                method="memory_remember",
                keywords=("remember", "store", "memory"),
                aliases=("memory_remember",),
            ),
            RuntimeCapability(
                name="memory.show",
                description="Read a runtime memory value.",
                source="operation",
                method="memory_show",
                keywords=("show", "read", "memory"),
                aliases=("memory_show",),
            ),
            RuntimeCapability(
                name="memory.forget",
                description="Forget a runtime memory value.",
                source="operation",
                method="memory_forget",
                keywords=("forget", "delete", "memory"),
                aliases=("memory_forget",),
            ),
            RuntimeCapability(
                name="help",
                method="help",
                description="Show available runtime capabilities.",
                source="operation",
                keywords=("help", "capabilities", "commands"),
            ),
        )
        missing = [item.method for item in operations if item.method and not callable(getattr(self, item.method, None))]
        if missing:
            raise RuntimeError(f"runtime capability registry references missing methods: {', '.join(missing)}")
        return operations

    def _tool_capabilities(self) -> tuple[RuntimeCapability, ...]:
        capabilities: list[RuntimeCapability] = []
        tool_registry = self.runtime.tool_registry
        for metadata in tool_registry.discover():
            keywords = _TOOL_KEYWORDS.get(metadata.identifier, ())
            aliases = _TOOL_ALIASES.get(metadata.identifier, ())
            for capability_name in metadata.capability_values:
                capabilities.append(
                    RuntimeCapability(
                        name=capability_name,
                        description=metadata.description,
                        source="tool",
                        tool_id=metadata.identifier,
                        tool_capability=capability_name,
                        keywords=keywords + tuple(part for part in capability_name.replace(".", " ").split() if part),
                        aliases=aliases,
                        metadata={"tool_name": metadata.name},
                    )
                )
        return tuple(capabilities)

    def _tool_inputs(self, capability: RuntimeCapability, inputs: Mapping[str, Any], message: str) -> dict[str, Any]:
        prepared = dict(inputs)
        tool_id = capability.tool_id or ""
        config = self._config()
        repository = config.repositories[0] if config.repositories else None
        if tool_id == "repository.search":
            prepared.setdefault("path", str(config.workspace))
            prepared.setdefault("query", self._search_query(message))
        elif tool_id == "repository.metadata":
            prepared.setdefault("path", str(config.workspace))
        elif tool_id == "browser.automation":
            prepared.setdefault("action", self._browser_action(prepared, message))
            if prepared.get("action") == "open_url" and "url" not in prepared:
                prepared["url"] = self._browser_url(message, prepared)
        elif tool_id == "engineering.pipeline":
            if repository is None:
                raise ValueError("no configured repository is available for engineering.pipeline")
            prepared.setdefault("repository", repository.full_name)
            prepared.setdefault("issue_number", self._issue_number(inputs, message))
            prepared.setdefault("issue_title", f"Issue #{prepared['issue_number']}")
            prepared.setdefault("repository_path", str(self.runtime.configuration.github.workspace_path / repository.name))
            prepared.setdefault("run_tests", True)
        elif tool_id == "github.issue":
            if repository is None:
                raise ValueError("no configured repository is available for github.issue")
            prepared.setdefault("owner", repository.owner)
            prepared.setdefault("repo", repository.name)
        elif tool_id == "github.repository":
            if repository is None:
                raise ValueError("no configured repository is available for github.repository")
            prepared.setdefault("owner", repository.owner)
            prepared.setdefault("repo", repository.name)
        if not prepared:
            prepared["message"] = message
        return prepared

    def _tool_context(self):
        config = self._config()
        repository = config.repositories[0] if config.repositories else None
        repo_ref = RepositoryRef(
            provider="github",
            owner=repository.owner if repository else "local",
            name=repository.name if repository else "workspace",
            default_branch=repository.default_branch if repository else config.default_branch,
        )
        issue_ref = IssueRef(provider="runtime", repository=repo_ref.full_name, issue_number=0, title="Runtime request")
        return self.runtime.create_context(issue=issue_ref, repository=repo_ref)

    def _config(self) -> WorkerConfiguration:
        assert self.loader is not None
        _, config = self.loader.load()
        return config

    def _repository_name(self, repository: object | None, config: WorkerConfiguration) -> str:
        return str(repository or (config.repositories[0].full_name if config.repositories else ""))

    def _resolution_text(self, requested: str, message: str) -> str:
        return " ".join((requested, message)).lower().replace("_", " ").replace("-", " ")

    def _normalize_capability_name(self, requested: str) -> str:
        return re.sub(r"[^a-z0-9_.]+", "_", requested.strip().lower().replace("-", "_")).strip("_")

    def _capability_score(self, capability: RuntimeCapability, text: str, inputs: Mapping[str, Any]) -> float:
        words = set(re.findall(r"[a-z0-9]+", text))
        keyword_hits = sum(1 for keyword in capability.keywords if keyword in words or keyword in text)
        alias_hits = sum(2 for alias in capability.aliases if alias.replace("_", " ") in text or alias == self._normalize_capability_name(text))
        score = float(keyword_hits + alias_hits)
        if capability.requires_issue_number and self._has_issue_number(inputs, text):
            score += 2.0
        if capability.requires_description and ("create" in words or "new" in words) and "issue" in words:
            score += 2.0
        if capability.name == "retry_latest_failed" and "retry" in words and not self._has_issue_number(inputs, text):
            score += 2.0
        if capability.name == "clear_queue" and words & {"clear", "empty"} and "queue" in words:
            score += 5.0
        if capability.name == "remove_issue" and words & {"remove", "delete"} and "issue" in words:
            score += 5.0
        if capability.name == "cancel_issue" and "cancel" in words and "issue" in words:
            score += 5.0
        if capability.name == "restart_issue" and "restart" in words and "issue" in words:
            score += 5.0
        if capability.name == "run_issue_now" and words & {"run", "work"} and ("now" in words or "immediately" in words):
            score += 5.0
        if capability.name == "prioritize_issue" and words & {"prioritize", "priority"} and "issue" in words:
            score += 5.0
        if capability.name == "move_issue_to_front" and words & {"move", "front"} and "issue" in words:
            score += 5.0
        if capability.name == "show_current_job" and (("doing" in words) or ("current" in words and words & {"job", "task"})):
            score += 5.0
        if capability.name == "show_worker_state" and words & {"worker", "status", "state"}:
            score += 4.0
        if capability.name == "stop_current_job" and words & {"stop", "halt"} and words & {"current", "task", "job"}:
            score += 5.0
        if capability.name == "resume_current_job" and words & {"continue", "resume"} and words & {"working", "job"}:
            score += 5.0
        if capability.name == "clear_retry_state" and (({"reset", "retry"} & words) or ("reset" in words and "issue" in words)):
            score += 5.0
        if capability.name == "clear_history" and words & {"forget", "history", "attempt"} and "issue" in words:
            score += 5.0
        if capability.name == "check_now" and "github" in words and ("check" in words or "run" in words):
            score += 2.0
        if capability.name in {"status", "queue", "list_queue"} and words & {"status", "queue"}:
            score += 2.0
        if capability.name == "health" and "health" in words:
            score += 3.0
        if capability.tool_id == "repository.search" and words & {"search", "repository", "repo", "code"}:
            score += 3.0
        if capability.tool_id == "browser.automation" and words & {"browser", "open", "page", "website"}:
            score += 3.0
        if capability.name == "browser.navigate" and words & {"open", "website", "page", "github"}:
            score += 2.0
        if capability.name == "browser.launch" and "launch" in words:
            score += 1.0
        if capability.tool_id == "engineering.pipeline" and words & {"pipeline", "engineering"}:
            score += 2.0
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

    def _search_query(self, message: str) -> str:
        match = re.search(r"(?:search|find|look for)\s+(?:the\s+)?(?:repository|repo|code)?\s*(.+)$", message, re.IGNORECASE)
        query = match.group(1).strip() if match else ""
        return query or "TODO"

    def _browser_action(self, inputs: Mapping[str, Any], message: str) -> str:
        if inputs.get("action"):
            return str(inputs["action"])
        if any(term in message.lower() for term in ("screenshot", "capture")):
            return "take_screenshot"
        if any(term in message.lower() for term in ("read", "text", "summarize")):
            return "read_visible_text"
        return "open_url"

    def _browser_url(self, message: str, inputs: Mapping[str, Any]) -> str:
        if inputs.get("query"):
            return f"https://www.google.com/search?q={str(inputs['query']).replace(' ', '+')}"
        match = re.search(r"(https?://\S+)", message)
        if match:
            return match.group(1)
        return "https://www.google.com"

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

    def _issue_key(self, issue_number: int, *, repository: object | None = None) -> str:
        config = self._config()
        repo_name = self._repository_name(repository, config)
        return f"{repo_name}#{issue_number}"

    def _load_worker_issue(self, issue_number: int, *, repository: object | None = None, attempts: int = 0) -> WorkerIssue:
        config = self._config()
        repo_name = self._repository_name(repository, config)
        if not repo_name:
            raise ValueError("No repository is configured for GitHub issue execution.")
        owner, name = repo_name.split("/", 1)
        github_config = GitHubIntegrationConfig.from_environment()
        service = IssueService(GitHubClient(github_config))
        issue = service.read_issue(owner, name, issue_number)
        return WorkerIssue(
            repository=repo_name,
            number=issue.number,
            title=issue.title,
            url=issue.html_url,
            labels=issue.labels,
            attempts=attempts,
            metadata={"body": issue.body or "", "comments": issue.comments, "author": issue.user_login or ""},
        )

    def _failure_response(self, *, stage: str, reason: str, suggested_action: str) -> str:
        return "\n".join((f"Stage: {stage}", f"Reason: {reason}", f"Suggested action: {suggested_action}"))

    def _clear_retry_state(self, issue_key: str, *, config: WorkerConfiguration) -> bool:
        store = ProcessedIssueStore(config.processed_issue_history)
        return store.remove(issue_key)

    def _clear_history(self, issue_key: str, *, config: WorkerConfiguration) -> bool:
        changed = False
        store = ProcessedIssueStore(config.processed_issue_history)
        changed = store.remove(issue_key) or changed
        changed = self._clear_reports(issue_key, config=config) or changed
        return changed

    def _clear_workspace(self, issue_key: str, *, config: WorkerConfiguration) -> bool:
        repository, _ = issue_key.rsplit("#", 1)
        runtime_github = getattr(getattr(self.runtime, "configuration", None), "github", None)
        github_config = GitHubIntegrationConfig.from_environment(
            workspace_path=getattr(runtime_github, "workspace_path", Path(".workspaces")),
            cleanup_policy=getattr(runtime_github, "cleanup_policy", "delete"),
        )
        manager = RepositoryWorkspaceManager(github_config)
        target = manager.repository_path(repository)
        if not target.exists():
            return False
        manager.cleanup(target, force=True)
        return True

    def _clear_reports(self, issue_key: str, *, config: WorkerConfiguration) -> bool:
        repository, issue_number_text = issue_key.rsplit("#", 1)
        issue_number = int(issue_number_text)
        directory = config.decisions.report_directory
        if not directory.exists():
            return False
        removed = False
        for path in directory.glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            report_repository = str(payload.get("repository") or payload.get("repository_name") or "")
            issue_summary = str(payload.get("issue_summary") or "")
            if report_repository != repository:
                continue
            if f"#{issue_number}" not in issue_summary:
                continue
            path.unlink()
            removed = True
        return removed

    def _running_text(self, status: dict[str, Any]) -> str:
        if self.is_paused():
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

    def _worker_version(self) -> str:
        try:
            from importlib.metadata import version

            return version("github-engineering-worker")
        except Exception:
            return "0.1.0"

    def _git_commit(self) -> str:
        try:
            result = subprocess.run(
                ("git", "rev-parse", "--short", "HEAD"),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
                check=False,
            )
        except Exception:
            return "unknown"
        return result.stdout.strip() or "unknown"


_TOOL_KEYWORDS: dict[str, tuple[str, ...]] = {
    "browser.automation": ("browser", "page", "website", "navigate", "read", "search"),
    "repository.search": ("repository", "repo", "search", "code", "symbol"),
    "repository.metadata": ("repository", "metadata", "context"),
    "engineering.pipeline": ("engineering", "pipeline", "solve", "fix", "patch"),
    "github.issue": ("github", "issue", "create", "read", "list"),
    "github.commit": ("commit", "push", "rollback", "git"),
    "github.pull_request": ("pull", "request", "pr", "github"),
}

_TOOL_ALIASES: dict[str, tuple[str, ...]] = {
    "browser.automation": ("run_browser", "browser_automation"),
    "repository.search": ("search_repository", "repo_search"),
    "repository.metadata": ("repository_context",),
    "engineering.pipeline": ("engineering_pipeline",),
}
