"""Repository watcher that discovers open GitHub issues."""

from __future__ import annotations

import json
from pathlib import Path
from threading import RLock

from github.issues import IssueService
from worker.models import WorkerIssue, WorkerRepository
from worker.queue import PersistentIssueQueue


class ProcessedIssueStore:
    """JSON-backed processed issue history."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = RLock()
        self._processed = self._load()

    def contains(self, issue_key: str) -> bool:
        with self._lock:
            return issue_key in self._processed

    def mark_processed(self, issue_key: str, *, status: str = "completed") -> None:
        with self._lock:
            self._processed[issue_key] = {"status": status}
            self._save()

    def keys(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._processed))

    def remove(self, issue_key: str) -> bool:
        with self._lock:
            if issue_key not in self._processed:
                return False
            del self._processed[issue_key]
            self._save()
            return True

    def clear(self) -> tuple[str, ...]:
        with self._lock:
            cleared = tuple(sorted(self._processed))
            self._processed = {}
            self._save()
            return cleared

    def status_for(self, issue_key: str) -> str | None:
        with self._lock:
            data = self._processed.get(issue_key)
            if data is None:
                return None
            return str(data.get("status") or "")

    def _load(self) -> dict[str, dict[str, str]]:
        if not self.path.exists():
            return {}
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return {str(key): dict(value) for key, value in data.get("processed", {}).items()}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"processed": self._processed}, indent=2, sort_keys=True), encoding="utf-8")


class GitHubIssueWatcher:
    """Fetches open issues and enqueues unseen work."""

    def __init__(
        self,
        *,
        issue_service: IssueService,
        queue: PersistentIssueQueue,
        processed_store: ProcessedIssueStore,
        repositories: tuple[WorkerRepository, ...],
        limit: int = 30,
    ) -> None:
        self.issue_service = issue_service
        self.queue = queue
        self.processed_store = processed_store
        self.repositories = repositories
        self.limit = limit
        self.in_progress: set[str] = set()

    def poll(self) -> tuple[WorkerIssue, ...]:
        enqueued: list[WorkerIssue] = []
        for repository in self.repositories:
            for issue in self.issue_service.list_open_issues(repository.owner, repository.name, limit=self.limit):
                if issue.state.lower() != "open" or issue.pull_request:
                    continue
                worker_issue = WorkerIssue(
                    repository=repository.full_name,
                    number=issue.number,
                    title=issue.title,
                    url=issue.html_url,
                    labels=issue.labels,
                    metadata={"body": issue.body or "", "comments": issue.comments, "author": issue.user_login or ""},
                )
                if self.should_skip(worker_issue.key):
                    continue
                if self.queue.enqueue(worker_issue):
                    enqueued.append(worker_issue)
        return tuple(enqueued)

    def should_skip(self, issue_key: str) -> bool:
        return self.processed_store.contains(issue_key) or issue_key in self.in_progress or self.queue.contains(issue_key)

    def mark_in_progress(self, issue_key: str) -> None:
        self.in_progress.add(issue_key)

    def clear_in_progress(self, issue_key: str) -> None:
        self.in_progress.discard(issue_key)
