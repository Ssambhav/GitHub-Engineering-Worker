"""Sequential persistent issue queue."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any

from worker.models import WorkerIssue


class PersistentIssueQueue:
    """FIFO issue queue with duplicate prevention and JSON persistence."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = RLock()
        self._items: list[WorkerIssue] = []
        self._load()

    def enqueue(self, issue: WorkerIssue) -> bool:
        with self._lock:
            if self.contains(issue.key):
                return False
            self._items.append(issue)
            self._save()
            return True

    def retry_enqueue(self, issue: WorkerIssue) -> bool:
        retry_issue = WorkerIssue(
            repository=issue.repository,
            number=issue.number,
            title=issue.title,
            url=issue.url,
            labels=issue.labels,
            attempts=issue.attempts + 1,
            metadata=issue.metadata,
        )
        return self.enqueue(retry_issue)

    def dequeue(self) -> WorkerIssue | None:
        with self._lock:
            if not self._items:
                return None
            issue = self._items.pop(0)
            self._save()
            return issue

    def dequeue_issue(self, issue_key: str) -> WorkerIssue | None:
        with self._lock:
            for index, issue in enumerate(self._items):
                if issue.key != issue_key:
                    continue
                matched = self._items.pop(index)
                self._save()
                return matched
            return None

    def clear(self) -> tuple[WorkerIssue, ...]:
        with self._lock:
            cleared = tuple(self._items)
            self._items = []
            self._save()
            return cleared

    def move_to_front(self, issue_key: str) -> WorkerIssue | None:
        with self._lock:
            for index, issue in enumerate(self._items):
                if issue.key != issue_key:
                    continue
                matched = self._items.pop(index)
                self._items.insert(0, matched)
                self._save()
                return matched
            return None

    def items(self) -> tuple[WorkerIssue, ...]:
        with self._lock:
            return tuple(self._items)

    def peek(self) -> WorkerIssue | None:
        with self._lock:
            return self._items[0] if self._items else None

    def contains(self, issue_key: str) -> bool:
        return any(item.key == issue_key for item in self._items)

    def keys(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(item.key for item in self._items)

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)

    def _load(self) -> None:
        if not self.path.exists():
            self._items = []
            return
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self._items = [_issue_from_json(item) for item in data.get("items", [])]

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"items": [_issue_to_json(item) for item in self._items]}
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _issue_to_json(issue: WorkerIssue) -> dict[str, Any]:
    return {
        "repository": issue.repository,
        "number": issue.number,
        "title": issue.title,
        "url": issue.url,
        "labels": list(issue.labels),
        "attempts": issue.attempts,
        "enqueued_at": issue.enqueued_at.isoformat(),
        "metadata": dict(issue.metadata),
    }


def _issue_from_json(data: dict[str, Any]) -> WorkerIssue:
    return WorkerIssue(
        repository=str(data["repository"]),
        number=int(data["number"]),
        title=data.get("title"),
        url=data.get("url"),
        labels=tuple(data.get("labels", ())),
        attempts=int(data.get("attempts", 0)),
        enqueued_at=datetime.fromisoformat(data["enqueued_at"]) if data.get("enqueued_at") else datetime.now(),
        metadata=data.get("metadata", {}),
    )
