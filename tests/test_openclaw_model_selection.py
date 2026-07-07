from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from engineering.models.core import Prompt, ProviderRequest
from engineering.openclaw_agent import OpenClawAgentExecutor
from engineering.configuration import EngineeringConfiguration
from engineering.models import EngineeringIssue
from engineering.providers.openclaw import OpenClawProvider


class OpenClawModelSelectionTests(unittest.TestCase):
    def test_generate_patch_passes_request_model_override_to_openclaw(self) -> None:
        provider = OpenClawProvider(cli="openclaw")
        prompt = Prompt(system="system", instructions=(), context_sections={}, desired_output_format="json")
        commands: list[list[str]] = []

        def fake_run(command: list[str]) -> dict[str, object]:
            commands.append(list(command))
            return {"ok": True, "outputs": [{"text": json.dumps({"patch": "ok"})}]}

        with patch.object(OpenClawProvider, "model_selection", return_value=type("Selection", (), {"resolved_model": "openai/gpt-5.4", "selected_provider": "openai"})()):
            with patch.object(OpenClawProvider, "_run", side_effect=fake_run):
                with patch("engineering.providers.openclaw.parse_patch_response", return_value=type("Patch", (), {"unified_diff": "", "engineering_summary": "ok", "confidence": 1.0, "modified_files": (), "reasoning_summary": "ok", "provider_name": "openclaw", "raw_text": "{}"})()):
                    provider.generate_patch(ProviderRequest(prompt=prompt, model="openai/gpt-5.4"))

        self.assertEqual("openai/gpt-5.4", provider.last_selected_model)
        self.assertEqual("openai", provider.last_selected_provider)
        self.assertTrue(commands)
        self.assertIn("--model", commands[0])
        self.assertIn("openai/gpt-5.4", commands[0])

    def test_infer_provider_passes_explicit_model_override_to_openclaw(self) -> None:
        provider = OpenClawProvider(cli="openclaw", model="openai/gpt-5.4")
        commands: list[list[str]] = []

        def fake_run(command: list[str]) -> dict[str, object]:
            commands.append(list(command))
            return {"ok": True, "outputs": [{"text": "ok"}]}

        with patch.object(OpenClawProvider, "model_selection", return_value=type("Selection", (), {"resolved_model": "google/gemini-2.5-flash", "selected_provider": "google"})()):
            with patch.object(OpenClawProvider, "_run", side_effect=fake_run):
                provider.infer_text("hello")

        self.assertEqual("openai/gpt-5.4", provider.last_selected_model)
        self.assertEqual("openai", provider.last_selected_provider)
        self.assertIn("--model", commands[0])
        self.assertIn("openai/gpt-5.4", commands[0])

    def test_agent_executor_passes_resolved_model_override_to_agent_cli(self) -> None:
        config = EngineeringConfiguration(openclaw_cli="openclaw")
        issue = EngineeringIssue(repository="acme/app", number=10, title="Fix issue #10")
        executor = OpenClawAgentExecutor(config)
        observed_commands: list[list[str]] = []

        def fake_run(command: list[str], *, cwd):
            observed_commands.append(list(command))
            return type(
                "Completed",
                (),
                {
                    "returncode": 0,
                    "stdout": json.dumps({"status": "ok", "result": {"finalAssistantRawText": json.dumps({"summary": "ok", "confidence": 0.9, "tests": [], "warnings": [], "errors": [], "remaining_limitations": [], "recommended_next_step": "review"}), "executionTrace": {"runner": "gateway", "winnerProvider": "openai"}}}),
                    "stderr": "",
                },
            )()

        with patch("engineering.openclaw_agent._read_model_selection", return_value=type("Selection", (), {"resolved_model": "openai/gpt-5.4", "selected_provider": "openai"})()):
            with patch.object(OpenClawAgentExecutor, "_run", side_effect=fake_run):
                with patch.object(OpenClawAgentExecutor, "_git_modified_files", return_value=()):
                    result = executor.execute(repository_path=__import__("pathlib").Path("."), issue=issue, run_tests=False)

        self.assertEqual("openai/gpt-5.4", result.execution_metadata.selected_model)
        self.assertEqual("openai", result.execution_metadata.selected_provider)
        self.assertTrue(observed_commands)
        self.assertIn("--model", observed_commands[0])
        self.assertIn("openai/gpt-5.4", observed_commands[0])

    def test_agent_executor_reports_stderr_when_agent_cli_exits_nonzero(self) -> None:
        config = EngineeringConfiguration(openclaw_cli="openclaw")
        issue = EngineeringIssue(repository="acme/app", number=10, title="Fix issue #10")
        executor = OpenClawAgentExecutor(config)

        def fake_run(command: list[str], *, cwd):
            return type("Completed", (), {"returncode": 1, "stdout": "", "stderr": "GatewayClientRequestError: quota exceeded"})()

        with patch("engineering.openclaw_agent._read_model_selection", return_value=type("Selection", (), {"resolved_model": "openai/gpt-5.4", "selected_provider": "openai"})()):
            with patch.object(OpenClawAgentExecutor, "_run", side_effect=fake_run):
                with patch.object(OpenClawAgentExecutor, "_git_modified_files", return_value=()):
                    with self.assertRaisesRegex(RuntimeError, "quota exceeded"):
                        executor.execute(repository_path=__import__("pathlib").Path("."), issue=issue, run_tests=False)


if __name__ == "__main__":
    unittest.main()
