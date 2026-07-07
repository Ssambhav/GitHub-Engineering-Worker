from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from confidence import ConfidenceEngine
from engineering.models import EngineeringResult, TestCommand, TestResult
from escalation.engine import EscalationEngine
from github.configuration import GitHubIntegrationConfig
from reports import EngineeringReportGenerator
from worker.configuration.models import WorkerConfiguration, WorkerDecisionConfiguration
from worker.controller import PipelineController
from worker.models import WorkerIssue, WorkerRepository


class VerificationLoopControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        decisions = WorkerDecisionConfiguration(
            audit_directory=root / "audit",
            report_directory=root / "reports",
            run_tests=False,
            auto_commit=True,
            auto_push=True,
            auto_create_pr=True,
            confidence_threshold=0.0,
        )
        self.config = WorkerConfiguration(workspace=root, max_retries=0, decisions=decisions)
        self.github_config = GitHubIntegrationConfig(workspace_path=root / ".workspaces")
        self.github_client = Mock()
        self.github_client.get_repository.return_value = object()
        self.audit_logger = Mock()
        self.notifications = Mock()
        self.escalation_engine = EscalationEngine()
        self.controller = PipelineController(
            config=self.config,
            github_config=self.github_config,
            github_client=self.github_client,
            confidence_engine=ConfidenceEngine(),
            audit_logger=self.audit_logger,
            report_generator=EngineeringReportGenerator(),
            escalation_engine=self.escalation_engine,
            notifications=self.notifications,
            runtime=SimpleNamespace(configuration=None),
        )
    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _issue(self) -> WorkerIssue:
        return WorkerIssue(
            repository="acme/app",
            number=12,
            title="Login banner never clears",
            url="https://github.com/acme/app/issues/12",
            metadata={"body": "Open http://localhost:3000/login. Expected: dashboard appears after login. Actual: error banner stays visible."},
        )

    def _repository(self) -> WorkerRepository:
        return WorkerRepository(owner="acme", name="app", default_branch="main")

    def _engineering_result(self) -> EngineeringResult:
        return EngineeringResult(
            issue=SimpleNamespace(repository="acme/app", number=12),
            repository="acme/app",
            patch_summary="Fix login banner state reset.",
            files_modified=("src/login.ts",),
            tests_executed=(TestCommand(("python", "-m", "pytest"), "tests detected"),),
            test_results=(TestResult(("python", "-m", "pytest"), 0, 25, "ok", "", True),),
            confidence=0.91,
            engineering_notes=("root cause confirmed",),
        )

    @patch("worker.controller.BranchService.create_issue_branch")
    @patch("worker.controller.GitWorkflow.create")
    @patch("worker.controller.EngineeringExecutionPipeline.create")
    @patch("worker.controller.RepositoryWorkspaceManager")
    def test_no_repository_changes_escalate_instead_of_creating_pr(
        self,
        workspace_cls: Mock,
        pipeline_create: Mock,
        git_create: Mock,
        create_branch: Mock,
    ) -> None:
        repo_path = Path(self.tmp.name) / "repo"
        repo_path.mkdir()
        workspace = workspace_cls.return_value
        workspace.clone_or_reuse.return_value = repo_path
        pipeline = pipeline_create.return_value
        pipeline.run_until_patch.return_value = EngineeringResult(
            issue=SimpleNamespace(repository="acme/app", number=12),
            repository="acme/app",
            patch_summary="No safe fix could be determined.",
            files_modified=(),
            tests_executed=(),
            test_results=(),
            confidence=0.31,
            errors=("unable to identify the failing code path",),
        )

        result = self.controller.execute(self._issue(), self._repository())

        self.assertEqual("escalated", result.status)
        self.assertIsNone(result.git_result)
        git_create.assert_not_called()
        create_branch.assert_called_once()
        self.assertEqual("No safe fix could be determined.", result.report.why_fixed)
        self.assertIn("unable to identify the failing code path", result.escalation.reasons)
        self.assertIn("Queue", [entry.stage_name for entry in result.report.execution_timeline])
        self.assertIn("Discord notification", [entry.stage_name for entry in result.report.execution_timeline])

    @patch("worker.controller.RepositoryWorkspaceManager")
    def test_controller_exception_reports_specific_failure_reason(self, workspace_cls: Mock) -> None:
        workspace = workspace_cls.return_value
        workspace.clone_or_reuse.side_effect = RuntimeError("git clone failed: auth required")

        result = self.controller.execute(self._issue(), self._repository())

        self.assertEqual("failed", result.status)
        self.assertIn("controller exception: RuntimeError: git clone failed: auth required", result.escalation.reasons)
        failed_stage = next(entry for entry in result.report.execution_timeline if entry.status == "FAIL")
        self.assertEqual("Repository checkout", failed_stage.stage_name)
        self.assertEqual("RuntimeError: git clone failed: auth required", failed_stage.exception)

    @patch("worker.controller.BranchService.create_issue_branch")
    @patch("worker.controller.GitWorkflow.create")
    @patch("worker.controller.EngineeringExecutionPipeline.create")
    @patch("worker.controller.RepositoryWorkspaceManager")
    def test_repository_changes_create_pr_without_verification_gate(
        self,
        workspace_cls: Mock,
        pipeline_create: Mock,
        git_create: Mock,
        create_branch: Mock,
    ) -> None:
        repo_path = Path(self.tmp.name) / "repo"
        repo_path.mkdir()
        workspace = workspace_cls.return_value
        workspace.clone_or_reuse.return_value = repo_path
        pipeline = pipeline_create.return_value
        pipeline.run_until_patch.return_value = self._engineering_result()
        git = git_create.return_value
        git.operations.current_branch.return_value = "gew/issue-12-login-banner"
        git.operations.changed_files.return_value = ("src/login.ts",)
        git.commit_service.create_commit.return_value = "abc123"
        git.pull_request_service.create_pr.return_value = SimpleNamespace(html_url="https://github.com/acme/app/pull/9")

        result = self.controller.execute(self._issue(), self._repository())

        self.assertEqual("dry_run_pr_created", result.status)
        self.assertIsNotNone(result.git_result)
        create_branch.assert_called_once()
        git.commit_service.create_commit.assert_called_once()
        git.operations.push_branch.assert_called_once()
        git.pull_request_service.create_pr.assert_called_once()
        self.assertEqual("Fix login banner state reset.", result.report.why_fixed)
        self.assertEqual("tests passed", result.report.validation)
        stage_names = [entry.stage_name for entry in result.report.execution_timeline]
        self.assertIn("OpenClaw Agent launch", stage_names)
        self.assertIn("OpenClaw Agent completion", stage_names)
        self.assertIn("Commit", stage_names)
        self.assertIn("Push", stage_names)
        self.assertIn("Pull Request", stage_names)
        self.assertIn("Discord notification", stage_names)


if __name__ == "__main__":
    unittest.main()
