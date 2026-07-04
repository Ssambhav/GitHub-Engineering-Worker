"""JSONL audit logger with query support."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from audit.models import AuditEntry, AuditQuery


class AuditLogger:
    """Append-only structured audit log."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.path = directory / "audit.jsonl"

    def append(self, entry: AuditEntry) -> AuditEntry:
        self.directory.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(_entry_to_json(entry), sort_keys=True) + "\n")
        return entry

    def query(self, query: AuditQuery | None = None) -> tuple[AuditEntry, ...]:
        if not self.path.exists():
            return ()
        query = query or AuditQuery()
        entries: list[AuditEntry] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            entry = _entry_from_json(json.loads(line))
            if _matches(entry, query):
                entries.append(entry)
        return tuple(entries)


def _matches(entry: AuditEntry, query: AuditQuery) -> bool:
    return all(
        (
            query.execution_id is None or entry.execution_id == query.execution_id,
            query.issue is None or entry.issue == query.issue,
            query.repository is None or entry.repository == query.repository,
            query.action is None or entry.action == query.action,
        )
    )


def _entry_to_json(entry: AuditEntry) -> dict[str, Any]:
    return {
        "audit_id": entry.audit_id,
        "timestamp": entry.timestamp.isoformat(),
        "execution_id": entry.execution_id,
        "issue": entry.issue,
        "repository": entry.repository,
        "current_stage": entry.current_stage,
        "current_agent": entry.current_agent,
        "current_tool": entry.current_tool,
        "action": entry.action,
        "decision": entry.decision,
        "confidence": entry.confidence,
        "retry_count": entry.retry_count,
        "files_modified": list(entry.files_modified),
        "tests_executed": list(entry.tests_executed),
        "execution_duration_ms": entry.execution_duration_ms,
        "result": entry.result,
        "metadata": dict(entry.metadata),
    }


def _entry_from_json(data: dict[str, Any]) -> AuditEntry:
    return AuditEntry(
        audit_id=str(data["audit_id"]),
        timestamp=datetime.fromisoformat(data["timestamp"]),
        execution_id=str(data["execution_id"]),
        issue=str(data["issue"]),
        repository=str(data["repository"]),
        current_stage=str(data["current_stage"]),
        current_agent=data.get("current_agent"),
        current_tool=data.get("current_tool"),
        action=str(data["action"]),
        decision=data.get("decision"),
        confidence=data.get("confidence"),
        retry_count=int(data.get("retry_count", 0)),
        files_modified=tuple(data.get("files_modified", ())),
        tests_executed=tuple(data.get("tests_executed", ())),
        execution_duration_ms=data.get("execution_duration_ms"),
        result=str(data["result"]),
        metadata=data.get("metadata", {}),
    )
