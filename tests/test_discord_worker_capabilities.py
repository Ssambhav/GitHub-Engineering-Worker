from __future__ import annotations

import unittest

from discord.ai_worker import DiscordAIWorker
from worker.runtime_interface import RuntimeCapability, WorkerRuntimeInterface


class RecordingWorker(WorkerRuntimeInterface):
    def __post_init__(self) -> None:
        self.calls: list[tuple[str, object | None]] = []

    def check_now(self) -> str:
        self.calls.append(("check_now", None))
        return "check_now"

    def status(self) -> str:
        self.calls.append(("status", None))
        return "status"

    def issues(self) -> str:
        self.calls.append(("issues", None))
        return "issues"

    def report(self) -> str:
        self.calls.append(("report", None))
        return "report"

    def retry_latest_failed(self) -> str:
        self.calls.append(("retry_latest_failed", None))
        return "retry_latest_failed"

    def retry_issue(self, issue_number: int, *, repository: object | None = None) -> str:
        self.calls.append(("retry_issue", issue_number))
        return "retry_issue"

    def solve_issue(self, issue_number: int, *, repository: object | None = None) -> str:
        self.calls.append(("solve_issue", issue_number))
        return "solve_issue"

    def create_issue(self, *, title: str, description: str, labels: tuple[str, ...] = (), repository: object | None = None) -> str:
        self.calls.append(("create_issue", title or description))
        return "create_issue"

    def health(self) -> str:
        self.calls.append(("health", None))
        return "health"

    def pause(self) -> str:
        self.calls.append(("pause", None))
        return "pause"

    def resume(self) -> str:
        self.calls.append(("resume", None))
        return "resume"

    def schedule(self, schedule_text: str) -> str:
        self.calls.append(("schedule", schedule_text))
        return "schedule"

    def help(self) -> str:
        self.calls.append(("help", None))
        return "help"


class DiscordWorkerCapabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.worker = RecordingWorker()
        self.bot = object.__new__(DiscordAIWorker)
        self.bot.worker = self.worker

    def test_runtime_capability_registry_references_real_methods(self) -> None:
        capabilities = WorkerRuntimeInterface.capabilities()
        self.assertIn("solve_issue", capabilities)
        self.assertIn("retry_issue", capabilities)
        self.assertIn("create_issue", capabilities)
        for capability in capabilities.values():
            self.assertIsInstance(capability, RuntimeCapability)
            self.assertTrue(callable(getattr(WorkerRuntimeInterface, capability.method, None)), capability.name)

    def test_natural_language_engineering_requests_resolve_to_registered_capabilities(self) -> None:
        cases = {
            "fix issue 4": "solve_issue",
            "solve issue #4": "solve_issue",
            "repair issue 4": "solve_issue",
            "work on issue 4": "solve_issue",
            "commit the fix": "solve_issue",
            "commit the fix for issue 4": "solve_issue",
            "retry issue 4": "retry_issue",
            "check github": "check_now",
            "create issue": "create_issue",
            "create github issue": "create_issue",
            "run worker": "check_now",
            "status": "status",
            "health": "health",
        }
        registered = set(self.worker.capabilities())
        for message, expected in cases.items():
            with self.subTest(message=message):
                resolution = self.worker.resolve_capability("", message=message, inputs={})
                self.assertTrue(resolution.supported, resolution)
                self.assertIn(resolution.capability.name, registered)
                self.assertEqual(expected, resolution.capability.name)

    def test_discord_worker_validation_canonicalizes_invented_operations(self) -> None:
        cases = {
            "fix issue 4": "solve_issue",
            "work on issue 4": "solve_issue",
            "repair issue 4": "solve_issue",
            "commit the fix for issue 4": "solve_issue",
            "run worker": "check_now",
            "check github": "check_now",
            "create github issue": "create_issue",
        }
        for message, expected in cases.items():
            with self.subTest(message=message):
                validation = DiscordAIWorker._validate_action(
                    self.bot,
                    "worker",
                    "whatever_the_model_invented",
                    {},
                    original_message=message,
                )
                self.assertTrue(validation["valid"], validation)
                self.assertEqual(expected, validation["operation"])

    def test_discord_worker_executes_only_canonical_capabilities(self) -> None:
        result = DiscordAIWorker._worker(self.bot, "whatever_the_model_invented", {}, original_message="fix issue 4")
        self.assertEqual("solve_issue", result)
        self.assertEqual([("solve_issue", 4)], self.worker.calls)

    def test_unsupported_worker_capability_returns_structured_response(self) -> None:
        validation = DiscordAIWorker._validate_action(self.bot, "worker", "deploy_production", {}, original_message="deploy production")
        self.assertFalse(validation["valid"])
        self.assertEqual("unsupported_capability", validation["status"])
        self.assertIn("available_capabilities", validation)


if __name__ == "__main__":
    unittest.main()
