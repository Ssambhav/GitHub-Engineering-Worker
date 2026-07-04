"""Run a local demonstration of the autonomous worker lifecycle."""

from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit import AuditLogger
from confidence import ConfidenceEngine, ConfidenceThresholds
from discord import DiscordWebhookProvider
from engineering.models import EngineeringResult, TestCommand, TestResult
from escalation import EscalationEngine, EscalationRules
from github.configuration import GitHubIntegrationConfig
from notifications import NotificationService
from reports import EngineeringReportGenerator
from worker.configuration.models import WorkerConfiguration, WorkerDecisionConfiguration
from worker.controller import PipelineController
from worker.models import WorkerIssue, WorkerRepository


class DemoGitHubClient:
    def get_repository(self, owner: str, name: str) -> object:
        return SimpleNamespace(owner=owner, name=name, full_name=f"{owner}/{name}", default_branch="main", clone_url="https://example.test/repo.git")


class DemoWorkspace:
    def __init__(self, config: GitHubIntegrationConfig) -> None:
        self.config = config

    def clone_or_reuse(self, repository: object) -> Path:
        return Path.cwd()

    def refresh(self, path: Path, branch: str) -> None:
        return None


class DemoGitWorkflow:
    @classmethod
    def create(cls, config: GitHubIntegrationConfig, pull_request_service: object) -> "DemoGitWorkflow":
        return cls()

    def complete_issue(self, **kwargs: object) -> object:
        return SimpleNamespace(branch="gew/issue-42-demo", commit_sha="demo123", pushed=False, pull_request=SimpleNamespace(dry_run=True), dry_run=True)


class SuccessfulPipeline:
    @classmethod
    def create(cls, config: object) -> "SuccessfulPipeline":
        return cls()

    def run_until_patch(self, *, repository_path: Path, issue: object, dry_run: bool, run_tests: bool) -> EngineeringResult:
        return EngineeringResult(
            issue=issue,
            repository=issue.repository,
            patch_summary="Demo patch generated and validated.",
            files_modified=("src/example.py", "tests/test_example.py"),
            tests_executed=(TestCommand(command=("pytest", "tests/test_example.py"), reason="demo"),),
            test_results=(TestResult(command=("pytest", "tests/test_example.py"), exit_code=0, duration_ms=12, stdout="1 passed", stderr="", passed=True),),
            confidence=0.9,
            warnings=(),
            errors=(),
            engineering_notes=("Demo root cause isolated.",),
            recommended_next_step="create_pr",
        )


class FailingPipeline(SuccessfulPipeline):
    def run_until_patch(self, *, repository_path: Path, issue: object, dry_run: bool, run_tests: bool) -> EngineeringResult:
        return EngineeringResult(
            issue=issue,
            repository=issue.repository,
            patch_summary="Demo patch failed validation.",
            files_modified=(),
            tests_executed=(),
            test_results=(),
            confidence=0.2,
            warnings=("insufficient context",),
            errors=("validation failed",),
            engineering_notes=("Repeated failure in demo.",),
            recommended_next_step="escalate",
        )


def main() -> int:
    import worker.controller as controller_mod

    controller_mod.RepositoryWorkspaceManager = DemoWorkspace
    controller_mod.GitWorkflow = DemoGitWorkflow

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        repo = WorkerRepository("demo-org", "demo-repo")
        decisions = WorkerDecisionConfiguration(
            confidence_thresholds=ConfidenceThresholds(proceed=70),
            audit_directory=root / "audit",
            report_directory=root / "reports",
            discord_enabled=True,
            discord_webhook=None,
            confidence_threshold=70,
            run_tests=True,
        )
        config = WorkerConfiguration(repositories=(repo,), provider="mock", decisions=decisions)
        base_kwargs = {
            "config": config,
            "github_config": GitHubIntegrationConfig(token=None),
            "github_client": DemoGitHubClient(),
            "audit_logger": AuditLogger(decisions.audit_directory),
            "report_generator": EngineeringReportGenerator(),
            "notifications": NotificationService(providers=(DiscordWebhookProvider(None),), enabled=True),
        }

        controller_mod.EngineeringExecutionPipeline = SuccessfulPipeline
        success = PipelineController(
            **base_kwargs,
            confidence_engine=ConfidenceEngine(decisions.confidence_thresholds),
            escalation_engine=EscalationEngine(EscalationRules(minimum_confidence=40, max_retries=3)),
        ).execute(WorkerIssue(repository=repo.full_name, number=42, title="Demo success"), repo)

        print("SUCCESS FLOW")
        print("Issue -> Repository -> Worker -> Patch -> Tests -> Pull Request")
        print(f"Status: {success.status}")
        print(f"Confidence: {success.confidence.overall if success.confidence else 'n/a'}")
        print()

        controller_mod.EngineeringExecutionPipeline = FailingPipeline
        failure = PipelineController(
            **base_kwargs,
            confidence_engine=ConfidenceEngine(decisions.confidence_thresholds),
            escalation_engine=EscalationEngine(EscalationRules(minimum_confidence=80, max_retries=2)),
        ).execute(WorkerIssue(repository=repo.full_name, number=77, title="Demo failure", attempts=3), repo)

        print("FAILURE FLOW")
        print("Issue -> Three failed attempts -> Confidence drops -> Escalation")
        print(f"Status: {failure.status}")
        print(f"Error: {failure.error or 'none'}")
        print(f"Report files: {len(list((root / 'reports').glob('*.json')))}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
