from __future__ import annotations

import re
import unittest
from dataclasses import replace

from discord.ai_worker import DiscordAIWorker
from engineering.providers.openclaw import OpenClawProvider
from worker.runtime_interface import CapabilityResolution, RuntimeCapability, WorkerRuntimeInterface


class RecordingWorker(WorkerRuntimeInterface):
    def __post_init__(self) -> None:
        self.calls: list[tuple[str, object | None]] = []
        self._capabilities = {
            "check_now": RuntimeCapability("check_now", "check", "operation", method="check_now", keywords=("check", "run", "worker")),
            "status": RuntimeCapability("status", "status", "operation", method="status", keywords=("status", "queue")),
            "clear_queue": RuntimeCapability("clear_queue", "clear queue", "operation", method="clear_queue", keywords=("clear", "empty", "queue")),
            "list_queue": RuntimeCapability("list_queue", "list queue", "operation", method="list_queue", keywords=("show", "list", "queue")),
            "issues": RuntimeCapability("issues", "issues", "operation", method="issues", keywords=("issues",)),
            "report": RuntimeCapability("report", "report", "operation", method="report", keywords=("report",)),
            "retry_latest_failed": RuntimeCapability("retry_latest_failed", "retry failed", "operation", method="retry_latest_failed", keywords=("retry", "failed")),
            "retry_issue": RuntimeCapability(
                "retry_issue",
                "retry issue",
                "operation",
                method="retry_issue",
                requires_issue_number=True,
                keywords=("retry", "issue"),
            ),
            "remove_issue": RuntimeCapability("remove_issue", "remove issue", "operation", method="remove_issue", requires_issue_number=True, keywords=("remove", "delete", "issue")),
            "cancel_issue": RuntimeCapability("cancel_issue", "cancel issue", "operation", method="cancel_issue", requires_issue_number=True, keywords=("cancel", "issue")),
            "restart_issue": RuntimeCapability("restart_issue", "restart issue", "operation", method="restart_issue", requires_issue_number=True, keywords=("restart", "reset", "issue")),
            "run_issue_now": RuntimeCapability("run_issue_now", "run now", "operation", method="run_issue_now", requires_issue_number=True, keywords=("run", "now", "issue")),
            "prioritize_issue": RuntimeCapability("prioritize_issue", "prioritize issue", "operation", method="prioritize_issue", requires_issue_number=True, keywords=("prioritize", "priority", "issue")),
            "move_issue_to_front": RuntimeCapability("move_issue_to_front", "move to front", "operation", method="move_issue_to_front", requires_issue_number=True, keywords=("move", "front", "issue")),
            "solve_issue": RuntimeCapability(
                "solve_issue",
                "solve issue",
                "operation",
                method="solve_issue",
                requires_issue_number=True,
                keywords=("fix", "solve", "repair", "work", "commit", "issue"),
            ),
            "create_issue": RuntimeCapability(
                "create_issue",
                "create issue",
                "operation",
                method="create_issue",
                requires_description=True,
                keywords=("create", "new", "issue"),
            ),
            "health": RuntimeCapability("health", "health", "operation", method="health", keywords=("health",)),
            "show_current_job": RuntimeCapability("show_current_job", "current job", "operation", method="show_current_job", keywords=("current", "job", "doing")),
            "show_worker_state": RuntimeCapability("show_worker_state", "worker state", "operation", method="show_worker_state", keywords=("worker", "status", "state")),
            "stop_current_job": RuntimeCapability("stop_current_job", "stop current job", "operation", method="stop_current_job", keywords=("stop", "current", "task")),
            "resume_current_job": RuntimeCapability("resume_current_job", "resume current job", "operation", method="resume_current_job", keywords=("continue", "resume", "working")),
            "pause": RuntimeCapability("pause", "pause", "operation", method="pause", keywords=("pause",)),
            "resume": RuntimeCapability("resume", "resume", "operation", method="resume", keywords=("resume",)),
            "schedule": RuntimeCapability("schedule", "schedule", "operation", method="schedule", keywords=("schedule", "every")),
            "clear_retry_state": RuntimeCapability("clear_retry_state", "clear retry state", "operation", method="clear_retry_state", requires_issue_number=True, keywords=("reset", "retry", "issue")),
            "clear_history": RuntimeCapability("clear_history", "clear history", "operation", method="clear_history", requires_issue_number=True, keywords=("forget", "history", "issue")),
            "help": RuntimeCapability("help", "help", "operation", method="help", keywords=("help",)),
            "repository.search": RuntimeCapability(
                "repository.search",
                "search repository",
                "tool",
                tool_id="repository.search",
                tool_capability="repository.search",
                keywords=("search", "repository", "repo", "code"),
                aliases=("search_repository",),
            ),
            "browser.navigate": RuntimeCapability(
                "browser.navigate",
                "browser",
                "tool",
                tool_id="browser.automation",
                tool_capability="browser.navigate",
                keywords=("browser", "open", "page"),
            ),
        }

    def capabilities(self) -> dict[str, RuntimeCapability]:
        return dict(self._capabilities)

    def resolve_capability(self, requested: str, *, message: str = "", inputs: dict | None = None) -> CapabilityResolution:
        text = f"{requested} {message}".lower()
        if requested in self._capabilities:
            capability = self._capabilities[requested]
            return CapabilityResolution(requested, capability, True, 1.0, "exact")
        if "search repository" in text:
            capability = self._capabilities["repository.search"]
            return CapabilityResolution(requested, capability, True, 0.9, "matched", (capability.name,))
        if "browser" in text:
            capability = self._capabilities["browser.navigate"]
            return CapabilityResolution(requested, capability, True, 0.9, "matched", (capability.name,))
        if "retry issue" in text:
            capability = self._capabilities["retry_issue"]
            return CapabilityResolution(requested, capability, True, 0.9, "matched", (capability.name,))
        if any(term in text for term in ("clear queue", "empty queue")):
            capability = self._capabilities["clear_queue"]
            return CapabilityResolution(requested, capability, True, 0.9, "matched", (capability.name,))
        if any(term in text for term in ("remove issue", "delete issue")):
            capability = self._capabilities["remove_issue"]
            return CapabilityResolution(requested, capability, True, 0.9, "matched", (capability.name,))
        if "cancel issue" in text:
            capability = self._capabilities["cancel_issue"]
            return CapabilityResolution(requested, capability, True, 0.9, "matched", (capability.name,))
        if "restart issue" in text:
            capability = self._capabilities["restart_issue"]
            return CapabilityResolution(requested, capability, True, 0.9, "matched", (capability.name,))
        if any(term in text for term in ("run issue", "work on issue")) and any(term in text for term in (" now", " immediately")):
            capability = self._capabilities["run_issue_now"]
            return CapabilityResolution(requested, capability, True, 0.9, "matched", (capability.name,))
        if "prioritize issue" in text:
            capability = self._capabilities["prioritize_issue"]
            return CapabilityResolution(requested, capability, True, 0.9, "matched", (capability.name,))
        if "move issue" in text and "front" in text:
            capability = self._capabilities["move_issue_to_front"]
            return CapabilityResolution(requested, capability, True, 0.9, "matched", (capability.name,))
        if any(term in text for term in ("what are you doing", "current job")):
            capability = self._capabilities["show_current_job"]
            return CapabilityResolution(requested, capability, True, 0.9, "matched", (capability.name,))
        if any(term in text for term in ("worker status", "worker state")):
            capability = self._capabilities["show_worker_state"]
            return CapabilityResolution(requested, capability, True, 0.9, "matched", (capability.name,))
        if any(term in text for term in ("stop current task", "stop current job")):
            capability = self._capabilities["stop_current_job"]
            return CapabilityResolution(requested, capability, True, 0.9, "matched", (capability.name,))
        if any(term in text for term in ("continue working", "resume current job")):
            capability = self._capabilities["resume_current_job"]
            return CapabilityResolution(requested, capability, True, 0.9, "matched", (capability.name,))
        if any(term in text for term in ("reset issue", "clear retry")):
            capability = self._capabilities["clear_retry_state"]
            return CapabilityResolution(requested, capability, True, 0.9, "matched", (capability.name,))
        if any(term in text for term in ("forget previous attempt", "clear history")):
            capability = self._capabilities["clear_history"]
            return CapabilityResolution(requested, capability, True, 0.9, "matched", (capability.name,))
        if any(term in text for term in ("fix issue", "solve issue", "repair issue", "work on issue", "commit the fix")):
            capability = self._capabilities["solve_issue"]
            return CapabilityResolution(requested, capability, True, 0.9, "matched", (capability.name,))
        if "check github" in text or "run worker" in text:
            capability = self._capabilities["check_now"]
            return CapabilityResolution(requested, capability, True, 0.8, "matched", (capability.name,))
        if "create" in text and "issue" in text:
            capability = self._capabilities["create_issue"]
            return CapabilityResolution(requested, capability, True, 0.8, "matched", (capability.name,))
        if "status" in text:
            capability = self._capabilities["status"]
            return CapabilityResolution(requested, capability, True, 0.8, "matched", (capability.name,))
        if "health" in text:
            capability = self._capabilities["health"]
            return CapabilityResolution(requested, capability, True, 0.8, "matched", (capability.name,))
        capability = self._capabilities["help"]
        return CapabilityResolution(requested, capability, False, 0.1, "unsupported", (capability.name,))

    def execute_capability(self, capability: RuntimeCapability, *, inputs: dict, message: str) -> str:
        if capability.source == "tool":
            self.calls.append((capability.name, inputs.get("query") or inputs.get("url")))
            return capability.name
        method = getattr(self, capability.method or "")
        if capability.requires_issue_number:
            issue_number = int(inputs.get("issue_number") or self._message_issue_number(message) or 4)
            return method(issue_number)
        if capability.name == "create_issue":
            return method(title=str(inputs.get("title") or ""), description=str(inputs.get("description") or message))
        if capability.name == "schedule":
            return method(str(inputs.get("schedule") or message))
        return method()

    def _message_issue_number(self, message: str) -> int | None:
        match = re.search(r"#(\d+)|issue\s+(\d+)", message, re.IGNORECASE)
        if not match:
            return None
        return int(next(value for value in match.groups() if value))

    def check_now(self) -> str:
        self.calls.append(("check_now", None))
        return "check_now"

    def status(self) -> str:
        self.calls.append(("status", None))
        return "status"

    def issues(self) -> str:
        self.calls.append(("issues", None))
        return "issues"

    def clear_queue(self) -> str:
        self.calls.append(("clear_queue", None))
        return "clear_queue"

    def list_queue(self) -> str:
        self.calls.append(("list_queue", None))
        return "list_queue"

    def report(self) -> str:
        self.calls.append(("report", None))
        return "report"

    def retry_latest_failed(self) -> str:
        self.calls.append(("retry_latest_failed", None))
        return "retry_latest_failed"

    def retry_issue(self, issue_number: int, *, repository: object | None = None) -> str:
        self.calls.append(("retry_issue", issue_number))
        return "retry_issue"

    def remove_issue(self, issue_number: int, *, repository: object | None = None) -> str:
        self.calls.append(("remove_issue", issue_number))
        return "remove_issue"

    def cancel_issue(self, issue_number: int, *, repository: object | None = None) -> str:
        self.calls.append(("cancel_issue", issue_number))
        return "cancel_issue"

    def restart_issue(self, issue_number: int, *, repository: object | None = None) -> str:
        self.calls.append(("restart_issue", issue_number))
        return "restart_issue"

    def run_issue_now(self, issue_number: int, *, repository: object | None = None) -> str:
        self.calls.append(("run_issue_now", issue_number))
        return "run_issue_now"

    def prioritize_issue(self, issue_number: int, *, repository: object | None = None) -> str:
        self.calls.append(("prioritize_issue", issue_number))
        return "prioritize_issue"

    def move_issue_to_front(self, issue_number: int, *, repository: object | None = None) -> str:
        self.calls.append(("move_issue_to_front", issue_number))
        return "move_issue_to_front"

    def solve_issue(self, issue_number: int, *, repository: object | None = None) -> str:
        self.calls.append(("solve_issue", issue_number))
        return "solve_issue"

    def create_issue(self, *, title: str, description: str, labels: tuple[str, ...] = (), repository: object | None = None) -> str:
        self.calls.append(("create_issue", title or description))
        return "create_issue"

    def health(self) -> str:
        self.calls.append(("health", None))
        return "health"

    def show_current_job(self) -> str:
        self.calls.append(("show_current_job", None))
        return "show_current_job"

    def show_worker_state(self) -> str:
        self.calls.append(("show_worker_state", None))
        return "show_worker_state"

    def stop_current_job(self) -> str:
        self.calls.append(("stop_current_job", None))
        return "stop_current_job"

    def resume_current_job(self) -> str:
        self.calls.append(("resume_current_job", None))
        return "resume_current_job"

    def pause(self) -> str:
        self.calls.append(("pause", None))
        return "pause"

    def resume(self) -> str:
        self.calls.append(("resume", None))
        return "resume"

    def schedule(self, schedule_text: str) -> str:
        self.calls.append(("schedule", schedule_text))
        return "schedule"

    def clear_retry_state(self, issue_number: int, *, repository: object | None = None) -> str:
        self.calls.append(("clear_retry_state", issue_number))
        return "clear_retry_state"

    def clear_history(self, issue_number: int, *, repository: object | None = None) -> str:
        self.calls.append(("clear_history", issue_number))
        return "clear_history"

    def help(self) -> str:
        self.calls.append(("help", None))
        return "help"


class DiscordWorkerCapabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.worker = RecordingWorker()
        self.bot = object.__new__(DiscordAIWorker)
        self.bot.worker = self.worker
        self.bot.audit_logger = None
        self.bot.memory = None
        self.bot.last_requests = {}

    def test_runtime_capability_registry_references_real_methods(self) -> None:
        capabilities = self.worker.capabilities()
        self.assertIn("solve_issue", capabilities)
        self.assertIn("retry_issue", capabilities)
        self.assertIn("create_issue", capabilities)
        for capability in capabilities.values():
            self.assertIsInstance(capability, RuntimeCapability)
            if capability.source == "operation":
                self.assertTrue(callable(getattr(RecordingWorker, capability.method, None)), capability.name)

    def test_natural_language_engineering_requests_resolve_to_registered_capabilities(self) -> None:
        cases = {
            "fix issue 4": "solve_issue",
            "solve issue #4": "solve_issue",
            "repair issue 4": "solve_issue",
            "work on issue 4": "solve_issue",
            "commit the fix": "solve_issue",
            "commit the fix for issue 4": "solve_issue",
            "clear queue": "clear_queue",
            "empty queue": "clear_queue",
            "remove issue #12": "remove_issue",
            "delete issue #12": "remove_issue",
            "cancel issue #12": "cancel_issue",
            "restart issue #12": "restart_issue",
            "retry issue 4": "retry_issue",
            "run issue #12 now": "run_issue_now",
            "work on issue #12 immediately": "run_issue_now",
            "prioritize issue #12": "prioritize_issue",
            "move issue #12 to front": "move_issue_to_front",
            "what are you doing": "show_current_job",
            "show worker status": "show_worker_state",
            "stop current task": "stop_current_job",
            "continue working": "resume_current_job",
            "reset issue #12": "clear_retry_state",
            "forget previous attempt issue #12": "clear_history",
            "check github": "check_now",
            "create issue": "create_issue",
            "create github issue": "create_issue",
            "run worker": "check_now",
            "status": "status",
            "health": "health",
            "search repository auth flow": "repository.search",
            "run browser on github.com": "browser.navigate",
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
            "clear queue": "clear_queue",
            "remove issue #12": "remove_issue",
            "restart issue #12": "restart_issue",
            "run issue #12 now": "run_issue_now",
            "run worker": "check_now",
            "check github": "check_now",
            "create github issue": "create_issue",
        }
        for message, expected in cases.items():
            with self.subTest(message=message):
                validation = DiscordAIWorker._validate_action(
                    self.bot,
                    "runtime",
                    "whatever_the_model_invented",
                    {},
                    original_message=message,
                )
                self.assertTrue(validation["valid"], validation)
                self.assertEqual(expected, validation["operation"])

    def test_discord_worker_executes_only_canonical_capabilities(self) -> None:
        result = DiscordAIWorker._runtime(self.bot, "whatever_the_model_invented", {}, original_message="fix issue 4")
        self.assertEqual("solve_issue", result)
        self.assertEqual([("solve_issue", 4)], self.worker.calls)

    def test_direct_runtime_plan_bypasses_chat_style_planning_for_worker_commands(self) -> None:
        plan = DiscordAIWorker._plan(self.bot, "remove issue #12")
        self.assertEqual("remove_issue", plan["actions"][0]["operation"])

    def test_direct_runtime_output_returns_runtime_result_verbatim(self) -> None:
        response = DiscordAIWorker._final_response(
            self.bot,
            "remove issue #12",
            {"actions": [{"tool": "runtime", "operation": "remove_issue", "inputs": {}}]},
            [{"tool": "runtime", "operation": "remove_issue", "success": True, "output": "Removed issue #12 from queue."}],
        )
        self.assertEqual("Removed issue #12 from queue.", response)

    def test_runtime_only_plan_returns_combined_runtime_outputs_without_ai_reply(self) -> None:
        response = DiscordAIWorker._final_response(
            self.bot,
            "pause and clear queue",
            {
                "actions": [
                    {"tool": "runtime", "operation": "pause", "inputs": {}},
                    {"tool": "runtime", "operation": "clear_queue", "inputs": {}},
                ]
            },
            [
                {"tool": "runtime", "operation": "pause", "success": True, "output": "Scheduler paused."},
                {"tool": "runtime", "operation": "clear_queue", "success": True, "output": "Cleared pending queue."},
            ],
        )
        self.assertEqual("Scheduler paused.\n\nCleared pending queue.", response)

    def test_runtime_owned_direct_command_does_not_call_openclaw_for_final_reply(self) -> None:
        bot = object.__new__(DiscordAIWorker)
        bot.worker = self.worker
        bot.audit_logger = None
        bot.memory = None
        bot.last_requests = {}

        class FailingOpenClaw:
            def infer_text(self, prompt: str) -> str:
                raise AssertionError(f"OpenClaw should not be called for runtime-owned response: {prompt}")

        bot.openclaw = FailingOpenClaw()
        response = DiscordAIWorker.respond(bot, "stop current task", user_id="u1", channel_id="c1")
        self.assertEqual("stop_current_job", response)
        self.assertEqual([("stop_current_job", None)], self.worker.calls)

    def test_discord_worker_normalizes_routing_categories_before_runtime_execution(self) -> None:
        observations = DiscordAIWorker._execute_plan(
            self.bot,
            {"actions": [{"tool": "general_ai|runtime", "operation": "runtime", "inputs": {}}]},
            message="Fix issue #8",
            user_id=None,
            channel_id=None,
        )
        self.assertEqual(1, len(observations))
        self.assertTrue(observations[0]["success"], observations)
        self.assertEqual("runtime", observations[0]["tool"])
        self.assertEqual("solve_issue", observations[0]["operation"])
        self.assertEqual("solve_issue", observations[0]["output"])
        self.assertEqual([("solve_issue", 8)], self.worker.calls)

    def test_unsupported_worker_capability_returns_structured_response(self) -> None:
        validation = DiscordAIWorker._validate_action(self.bot, "runtime", "deploy_production", {}, original_message="deploy production")
        self.assertFalse(validation["valid"])
        self.assertEqual("unresolved_runtime_request", validation["status"])
        self.assertIn("available_capabilities", validation)

    def test_google_quota_errors_return_openai_switch_hint(self) -> None:
        response = DiscordAIWorker._planning_error_response(
            self.bot,
            RuntimeError('OpenClaw planning failed: Error: No text output returned for provider "google" model "gemini-2.5-flash": quota exceeded'),
        )
        self.assertIn("WORKER_MODEL=openai/gpt-5.4", response)
        self.assertIn("OpenAI/Codex", response)

    def test_post_init_uses_worker_model_for_discord_openclaw_provider(self) -> None:
        bot = object.__new__(DiscordAIWorker)
        bot.openclaw = OpenClawProvider(model=None)
        bot.worker = self.worker
        bot.loader = type("Loader", (), {"load": lambda _self: (None, type("Config", (), {"model": "openai/gpt-5.4", "decisions": type("Decisions", (), {"audit_directory": __import__("pathlib").Path('audit/worker')})()})())})()
        bot.audit_logger = object()
        bot.memory = object()
        DiscordAIWorker.__post_init__(bot)
        self.assertEqual("openai/gpt-5.4", bot.openclaw.model)


if __name__ == "__main__":
    unittest.main()
