from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from confidence.models import ConfidenceThresholds
from escalation.models import EscalationRules
from github.models import GitHubIssue
from worker.configuration.models import WorkerConfiguration, WorkerDecisionConfiguration
from worker.models import WorkerIssue, WorkerRepository
from worker.runtime_interface import WorkerRuntimeInterface


class WorkerRuntimeInterfaceDispatchTests(unittest.TestCase):
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
        self.loader = SimpleNamespace(load=lambda: (None, self.config))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    @patch("worker.runtime_interface.IssueService")
    @patch("worker.runtime_interface.WorkerDaemon")
    def test_solve_issue_dispatches_requested_issue_even_when_queue_has_older_items(self, daemon_cls, issue_service_cls) -> None:
        queue_path = self.config.queue_persistence
        queue_path.parent.mkdir(parents=True, exist_ok=True)
        queue_path.write_text(
            (
                '{\n'
                '  "items": [\n'
                '    {"repository": "acme/app", "number": 10, "attempts": 0, "labels": [], "metadata": {}, "enqueued_at": "2026-07-06T23:00:00+00:00"}\n'
                "  ]\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        daemon = daemon_cls.return_value
        daemon.dispatch_issue_now.return_value = SimpleNamespace(status="retry_or_escalate")
        issue_service_cls.return_value.read_issue.return_value = GitHubIssue(
            number=12,
            title="Dark mode toggle does not switch application back to light mode",
            state="open",
            body="App URL: https://example.com\nExpected: theme switches back to light mode.",
            html_url="https://github.com/acme/app/issues/12",
            labels=("bug",),
            comments=3,
            user_login="sambhav",
            created_at=None,
            updated_at=None,
        )

        runtime = object.__new__(WorkerRuntimeInterface)
        runtime.loader = self.loader
        runtime.runtime = SimpleNamespace()

        result = WorkerRuntimeInterface.solve_issue(runtime, 12, repository="acme/app")

        self.assertEqual("Issue queued and executed: acme/app#12 (retry_or_escalate)", result)
        daemon.initialize.assert_called_once()
        daemon.dispatch_issue_now.assert_called_once_with("acme/app#12")
        text = self.config.queue_persistence.read_text(encoding="utf-8")
        self.assertIn('"title": "Dark mode toggle does not switch application back to light mode"', text)
        self.assertIn('"url": "https://github.com/acme/app/issues/12"', text)
        self.assertIn('"body": "App URL: https://example.com\\nExpected: theme switches back to light mode."', text)

    @patch("worker.runtime_interface.IssueService")
    @patch("worker.runtime_interface.WorkerDaemon")
    def test_retry_issue_executes_specific_issue_immediately(self, daemon_cls, issue_service_cls) -> None:
        daemon = daemon_cls.return_value
        daemon.dispatch_issue_now.return_value = SimpleNamespace(status="failed")
        issue_service_cls.return_value.read_issue.return_value = GitHubIssue(
            number=12,
            title="Dark mode toggle does not switch application back to light mode",
            state="open",
            body="App URL: https://example.com",
            html_url="https://github.com/acme/app/issues/12",
            labels=("bug",),
            comments=1,
            user_login="sambhav",
            created_at=None,
            updated_at=None,
        )

        runtime = object.__new__(WorkerRuntimeInterface)
        runtime.loader = self.loader
        runtime.runtime = SimpleNamespace()

        result = WorkerRuntimeInterface.retry_issue(runtime, 12, repository="acme/app")

        self.assertEqual("Retry queued and executed: acme/app#12 (failed)", result)
        daemon.initialize.assert_called_once()
        daemon.dispatch_issue_now.assert_called_once_with("acme/app#12")

    def test_clear_queue_removes_pending_items_and_keeps_current_job(self) -> None:
        self.config.queue_persistence.write_text(
            (
                '{\n'
                '  "items": [\n'
                '    {"repository": "acme/app", "number": 10, "attempts": 0, "labels": [], "metadata": {}, "enqueued_at": "2026-07-06T23:00:00+00:00"},\n'
                '    {"repository": "acme/app", "number": 12, "attempts": 0, "labels": [], "metadata": {}, "enqueued_at": "2026-07-06T23:01:00+00:00"}\n'
                "  ]\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        self.config.status_path.write_text('{"running": true, "current_issue": "acme/app#9"}', encoding="utf-8")
        runtime = object.__new__(WorkerRuntimeInterface)
        runtime.loader = self.loader
        runtime.runtime = SimpleNamespace()

        result = WorkerRuntimeInterface.clear_queue(runtime)

        self.assertIn("Removed: 2", result)
        self.assertIn("Running job: acme/app#9", result)
        self.assertIn('"items": []', self.config.queue_persistence.read_text(encoding="utf-8"))

    def test_remove_issue_deletes_only_requested_queue_entry(self) -> None:
        self.config.queue_persistence.write_text(
            (
                '{\n'
                '  "items": [\n'
                '    {"repository": "acme/app", "number": 10, "attempts": 0, "labels": [], "metadata": {}, "enqueued_at": "2026-07-06T23:00:00+00:00"},\n'
                '    {"repository": "acme/app", "number": 12, "attempts": 0, "labels": [], "metadata": {}, "enqueued_at": "2026-07-06T23:01:00+00:00"}\n'
                "  ]\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        runtime = object.__new__(WorkerRuntimeInterface)
        runtime.loader = self.loader
        runtime.runtime = SimpleNamespace()

        result = WorkerRuntimeInterface.remove_issue(runtime, 12, repository="acme/app")

        self.assertEqual("Removed acme/app#12 from queue.\nQueue size: 1", result)
        self.assertIn('"number": 10', self.config.queue_persistence.read_text(encoding="utf-8"))
        self.assertNotIn('"number": 12', self.config.queue_persistence.read_text(encoding="utf-8"))

    def test_prioritize_issue_moves_item_to_queue_front(self) -> None:
        self.config.queue_persistence.write_text(
            (
                '{\n'
                '  "items": [\n'
                '    {"repository": "acme/app", "number": 10, "attempts": 0, "labels": [], "metadata": {}, "enqueued_at": "2026-07-06T23:00:00+00:00"},\n'
                '    {"repository": "acme/app", "number": 12, "attempts": 0, "labels": [], "metadata": {}, "enqueued_at": "2026-07-06T23:01:00+00:00"}\n'
                "  ]\n"
                "}\n"
            ),
            encoding="utf-8",
        )
        runtime = object.__new__(WorkerRuntimeInterface)
        runtime.loader = self.loader
        runtime.runtime = SimpleNamespace()

        result = WorkerRuntimeInterface.prioritize_issue(runtime, 12, repository="acme/app")

        self.assertEqual("Moved acme/app#12 to the front of the queue.\nQueue size: 2", result)
        text = self.config.queue_persistence.read_text(encoding="utf-8")
        self.assertLess(text.index('"number": 12'), text.index('"number": 10'))

    @patch("worker.runtime_interface.IssueService")
    @patch("worker.runtime_interface.WorkerDaemon")
    def test_run_issue_now_dispatches_requested_issue_immediately(self, daemon_cls, issue_service_cls) -> None:
        daemon = daemon_cls.return_value
        daemon.dispatch_issue_now.return_value = SimpleNamespace(status="completed")
        issue_service_cls.return_value.read_issue.return_value = GitHubIssue(
            number=12,
            title="Dark mode toggle does not switch application back to light mode",
            state="open",
            body="App URL: https://example.com",
            html_url="https://github.com/acme/app/issues/12",
            labels=("bug",),
            comments=1,
            user_login="sambhav",
            created_at=None,
            updated_at=None,
        )
        runtime = object.__new__(WorkerRuntimeInterface)
        runtime.loader = self.loader
        runtime.runtime = SimpleNamespace()

        result = WorkerRuntimeInterface.run_issue_now(runtime, 12, repository="acme/app")

        self.assertEqual("Worker started on acme/app#12.\nDispatch result: completed.", result)
        daemon.initialize.assert_called_once()
        daemon.dispatch_issue_now.assert_called_once_with("acme/app#12")

    def test_show_current_job_reads_status_file(self) -> None:
        self.config.status_path.write_text(
            '{"running": true, "current_issue": "acme/app#12", "last_poll_at": "2026-07-07T00:00:00+00:00"}',
            encoding="utf-8",
        )
        runtime = object.__new__(WorkerRuntimeInterface)
        runtime.loader = self.loader
        runtime.runtime = SimpleNamespace()

        result = WorkerRuntimeInterface.show_current_job(runtime)

        self.assertIn("Current job: acme/app#12", result)
        self.assertIn("Worker status: running", result)

    def test_clear_retry_state_removes_processed_issue_entry(self) -> None:
        self.config.processed_issue_history.write_text(
            '{\n  "processed": {"acme/app#12": {"status": "escalated"}}\n}\n',
            encoding="utf-8",
        )
        runtime = object.__new__(WorkerRuntimeInterface)
        runtime.loader = self.loader
        runtime.runtime = SimpleNamespace()

        result = WorkerRuntimeInterface.clear_retry_state(runtime, 12, repository="acme/app")

        self.assertEqual("Retry state cleared for acme/app#12.", result)
        self.assertNotIn("acme/app#12", self.config.processed_issue_history.read_text(encoding="utf-8"))

    def test_clear_history_removes_matching_report_and_processed_entry(self) -> None:
        self.config.processed_issue_history.write_text(
            '{\n  "processed": {"acme/app#12": {"status": "failed"}}\n}\n',
            encoding="utf-8",
        )
        self.config.decisions.report_directory.mkdir(parents=True, exist_ok=True)
        report_path = self.config.decisions.report_directory / "report.json"
        report_path.write_text(
            '{\n  "repository": "acme/app",\n  "issue_summary": "Fix acme/app#12"\n}\n',
            encoding="utf-8",
        )
        runtime = object.__new__(WorkerRuntimeInterface)
        runtime.loader = self.loader
        runtime.runtime = SimpleNamespace()

        result = WorkerRuntimeInterface.clear_history(runtime, 12, repository="acme/app")

        self.assertEqual("Execution history cleared for acme/app#12.", result)
        self.assertFalse(report_path.exists())


if __name__ == "__main__":
    unittest.main()
