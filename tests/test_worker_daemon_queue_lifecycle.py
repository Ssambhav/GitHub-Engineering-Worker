from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from confidence.models import ConfidenceThresholds
from escalation.models import EscalationRules
from worker.configuration.models import WorkerConfiguration, WorkerDecisionConfiguration
from worker.daemon.daemon import WorkerDaemon
from worker.models import WorkerIssue, WorkerRepository
from worker.queue import PersistentIssueQueue
from worker.watcher.github import ProcessedIssueStore


class _WatcherStub:
    def __init__(self) -> None:
        self.in_progress: set[str] = set()

    def mark_in_progress(self, issue_key: str) -> None:
        self.in_progress.add(issue_key)

    def clear_in_progress(self, issue_key: str) -> None:
        self.in_progress.discard(issue_key)


class WorkerDaemonQueueLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        decisions = WorkerDecisionConfiguration(
            audit_directory=root / "audit",
            report_directory=root / "reports",
            confidence_thresholds=ConfidenceThresholds(),
            escalation_rules=EscalationRules(),
        )
        self.config = WorkerConfiguration(
            repositories=(WorkerRepository(owner="acme", name="app"),),
            queue_persistence=root / "queue.json",
            processed_issue_history=root / "processed.json",
            status_path=root / "status.json",
            decisions=decisions,
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _daemon(self) -> WorkerDaemon:
        daemon = object.__new__(WorkerDaemon)
        daemon.config = self.config
        daemon.queue = PersistentIssueQueue(self.config.queue_persistence)
        daemon.processed_store = ProcessedIssueStore(self.config.processed_issue_history)
        daemon.watcher = _WatcherStub()
        daemon.status = SimpleNamespace(current_issue=None, processed_count=0)
        daemon._write_status = lambda: None
        daemon._notify = lambda notification: None
        daemon._audit = lambda *args, **kwargs: None
        daemon._execute_issue = lambda issue: SimpleNamespace(succeeded=False, status="retry_or_escalate")
        return daemon

    def test_retry_or_escalate_does_not_requeue_issue(self) -> None:
        daemon = self._daemon()
        issue = WorkerIssue(repository="acme/app", number=12)

        result = WorkerDaemon._execute_queued_issue(daemon, issue)

        self.assertEqual("retry_or_escalate", result.status)
        self.assertEqual((), daemon.queue.items())
        self.assertEqual("retry_or_escalate", daemon.processed_store.status_for("acme/app#12"))
        self.assertIsNone(daemon.status.current_issue)
        self.assertNotIn("acme/app#12", daemon.watcher.in_progress)

    def test_terminal_retry_or_escalate_allows_fresh_requeue(self) -> None:
        daemon = self._daemon()
        issue = WorkerIssue(repository="acme/app", number=12)

        WorkerDaemon._execute_queued_issue(daemon, issue)
        first_enqueue = daemon.queue.enqueue(WorkerIssue(repository="acme/app", number=12, attempts=0))
        second_enqueue = daemon.queue.enqueue(WorkerIssue(repository="acme/app", number=12, attempts=0))

        self.assertTrue(first_enqueue)
        self.assertFalse(second_enqueue)
        queued = daemon.queue.items()
        self.assertEqual(1, len(queued))
        self.assertEqual(0, queued[0].attempts)


if __name__ == "__main__":
    unittest.main()
