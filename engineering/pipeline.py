"""Complete engineering execution pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from engineering.analysis import RepositoryAnalyzer
from engineering.configuration import EngineeringConfiguration
from engineering.context_builder import ContextBuilder
from engineering.models import EngineeringIssue, EngineeringResult
from engineering.models.core import ProviderRequest
from engineering.patch import PatchApplier, PatchValidator
from engineering.prompt_builder import PromptBuilder
from engineering.providers import ProviderFactory
from engineering.repository_search import RepositorySearcher
from engineering.testing import TestRuntime
from engineering.validation import RepositoryValidator


@dataclass(slots=True)
class EngineeringExecutionPipeline:
    """Runs issue understanding through dry-run or full patch application and tests."""

    config: EngineeringConfiguration
    searcher: RepositorySearcher
    context_builder: ContextBuilder
    prompt_builder: PromptBuilder
    provider_factory: ProviderFactory
    patch_validator: PatchValidator
    patch_applier: PatchApplier
    repository_validator: RepositoryValidator
    test_runtime: TestRuntime

    @classmethod
    def create(cls, config: EngineeringConfiguration | None = None) -> "EngineeringExecutionPipeline":
        config = config or EngineeringConfiguration()
        analyzer = RepositoryAnalyzer()
        return cls(
            config=config,
            searcher=RepositorySearcher(config),
            context_builder=ContextBuilder(config, analyzer),
            prompt_builder=PromptBuilder(),
            provider_factory=ProviderFactory(config),
            patch_validator=PatchValidator(config),
            patch_applier=PatchApplier(),
            repository_validator=RepositoryValidator(),
            test_runtime=TestRuntime(config),
        )

    def run_until_patch(
        self,
        *,
        repository_path: Path,
        issue: EngineeringIssue,
        dry_run: bool = True,
        run_tests: bool = False,
    ) -> EngineeringResult:
        candidates = self.searcher.search(repository_path, issue)
        context = self.context_builder.build(repository_path=repository_path, issue=issue, candidates=candidates)
        prompt = self.prompt_builder.build(context)
        provider = self.provider_factory.select()
        patch = provider.generate_patch(ProviderRequest(prompt=prompt, model=self.config.model))
        patch_validation = self.patch_validator.validate(repository_path, patch.unified_diff)
        errors = list(patch_validation.errors)
        application = None
        if patch_validation.valid:
            application = self.patch_applier.apply(repository_path, patch.unified_diff, dry_run=dry_run)
            errors.extend(application.errors)
        repo_warnings = self.repository_validator.validate(repository_path, patch_validation.modified_files)
        test_commands = self.test_runtime.detect(repository_path)
        test_results = self.test_runtime.run(repository_path, test_commands) if run_tests and not dry_run else ()
        recommended = "review_patch" if not errors else "retry_with_better_context"
        return EngineeringResult(
            issue=issue,
            repository=issue.repository,
            patch_summary=patch.engineering_summary,
            files_modified=patch_validation.modified_files,
            tests_executed=test_commands,
            test_results=test_results,
            confidence=min(patch.confidence, context.analysis.confidence),
            warnings=(*context.warnings, *patch_validation.warnings, *repo_warnings),
            errors=tuple(errors),
            engineering_notes=(patch.reasoning_summary, f"provider={patch.provider_name}", f"dry_run={dry_run}"),
            recommended_next_step=recommended,
        )
