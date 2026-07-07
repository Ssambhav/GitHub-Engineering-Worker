from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from engineering.configuration import EngineeringConfiguration
from engineering.models import EngineeringIssue
from engineering.models.core import EngineeringResult, ExecutionMetadata
from engineering.pipeline import EngineeringExecutionPipeline


class EngineeringReasoningPipelineTests(unittest.TestCase):
    def _pipeline(self, config: EngineeringConfiguration) -> EngineeringExecutionPipeline:
        return EngineeringExecutionPipeline.create(config)

    def test_agent_mode_is_primary_execution_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            issue = EngineeringIssue(repository="acme/app", number=10, title="Fix login banner")
            expected = EngineeringResult(
                issue=issue,
                repository=issue.repository,
                patch_summary="Agent fixed the issue.",
                files_modified=("src/login.ts",),
                tests_executed=(),
                test_results=(),
                confidence=0.9,
                execution_metadata=ExecutionMetadata(
                    mode="agent",
                    selected_reason="Agent mode selected.",
                    command=("openclaw", "agent"),
                    subprocess=("openclaw",),
                ),
            )
            config = EngineeringConfiguration(openclaw_agent_mode="agent", openclaw_agent_fallback_enabled=False)
            pipeline = self._pipeline(config)
            with patch("engineering.pipeline.OpenClawAgentCapabilityDetector.detect", return_value=Mock(callable=True, configured=True, command=("openclaw",), reason="ok")):
                with patch("engineering.pipeline.OpenClawAgentExecutor.execute", return_value=expected) as execute:
                    result = pipeline.run_until_patch(repository_path=root, issue=issue, dry_run=False, run_tests=True)
            self.assertEqual("agent", result.execution_metadata.mode)
            self.assertEqual("Agent fixed the issue.", result.patch_summary)
            execute.assert_called_once()

    def test_infer_fallback_is_explicit_when_agent_mode_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            issue = EngineeringIssue(repository="acme/app", number=11, title="Fix auth refresh")
            config = EngineeringConfiguration(openclaw_agent_mode="agent", openclaw_agent_fallback_enabled=True)
            pipeline = self._pipeline(config)
            fallback = EngineeringResult(
                issue=issue,
                repository=issue.repository,
                patch_summary="Infer fallback produced a patch.",
                files_modified=("src/auth.ts",),
                tests_executed=(),
                test_results=(),
                confidence=0.6,
                execution_metadata=ExecutionMetadata(
                    mode="infer",
                    selected_reason="Infer fallback.",
                    command=("openclaw", "infer"),
                    subprocess=("openclaw",),
                ),
            )
            with patch("engineering.pipeline.OpenClawAgentCapabilityDetector.detect", return_value=Mock(callable=True, configured=True, command=("openclaw",), reason="ok")):
                with patch("engineering.pipeline.OpenClawAgentExecutor.execute", side_effect=RuntimeError("agent failed")):
                    with patch.object(EngineeringExecutionPipeline, "_run_infer_pipeline", return_value=fallback):
                        result = pipeline.run_until_patch(repository_path=root, issue=issue, dry_run=False, run_tests=True)
            self.assertEqual("infer", result.execution_metadata.mode)
            self.assertEqual("agent failed", result.execution_metadata.fallback_reason)
            self.assertTrue(any("Fell back to infer mode" in warning for warning in result.warnings))


if __name__ == "__main__":
    unittest.main()
