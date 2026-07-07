"""Complete engineering execution pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from engineering.analysis import RepositoryAnalyzer
from engineering.configuration import EngineeringConfiguration
from engineering.context_builder import ContextBuilder
from engineering.openclaw_agent import OpenClawAgentCapabilityDetector, OpenClawAgentError, OpenClawAgentExecutor
from engineering.models import EngineeringIssue, EngineeringResult
from engineering.models.core import ExecutionMetadata
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
        if self.config.openclaw_agent_mode == "agent":
            capability = OpenClawAgentCapabilityDetector(
                cli=self.config.openclaw_cli,
                timeout_seconds=min(self.config.openclaw_timeout_seconds, 30),
            ).detect()
            if capability.callable and capability.configured:
                try:
                    return OpenClawAgentExecutor(self.config).execute(repository_path=repository_path, issue=issue, run_tests=run_tests)
                except Exception as exc:
                    if not self.config.openclaw_agent_fallback_enabled:
                        return EngineeringResult(
                            issue=issue,
                            repository=issue.repository,
                            patch_summary="OpenClaw Agent mode failed and infer fallback is disabled.",
                            files_modified=(),
                            tests_executed=(),
                            test_results=(),
                            confidence=0.0,
                            errors=(str(exc),),
                            engineering_notes=("mode=agent", "fallback=disabled"),
                            recommended_next_step="escalate",
                            execution_metadata=ExecutionMetadata(
                                mode="agent",
                                selected_reason="Agent mode was selected but execution failed.",
                                command=capability.command,
                                subprocess=capability.command,
                                fallback_reason="infer fallback disabled",
                                stage_exit_code=getattr(exc, "exit_code", None),
                                stage_stdout=str(getattr(exc, "stdout", "") or ""),
                                stage_stderr=str(getattr(exc, "stderr", "") or ""),
                                stage_exception=f"{exc.__class__.__name__}: {exc}",
                                stage_returned_value=str(getattr(exc, "returned_value", "") or ""),
                            ),
                        )
                    fallback = self._run_infer_pipeline(repository_path=repository_path, issue=issue, dry_run=dry_run, run_tests=run_tests)
                    return EngineeringResult(
                        issue=fallback.issue,
                        repository=fallback.repository,
                        patch_summary=fallback.patch_summary,
                        files_modified=fallback.files_modified,
                        tests_executed=fallback.tests_executed,
                        test_results=fallback.test_results,
                        confidence=fallback.confidence,
                        warnings=(*fallback.warnings, f"OpenClaw Agent mode failed: {exc}", "Fell back to infer mode for this attempt."),
                        errors=fallback.errors,
                        engineering_notes=(*fallback.engineering_notes, "mode=infer_fallback"),
                        recommended_next_step=fallback.recommended_next_step,
                        verification=fallback.verification,
                        execution_metadata=ExecutionMetadata(
                            mode="infer",
                            selected_reason="Infer mode was used only after Agent mode failed.",
                            command=fallback.execution_metadata.command if fallback.execution_metadata else (),
                            subprocess=fallback.execution_metadata.subprocess if fallback.execution_metadata else (),
                            fallback_reason=str(exc),
                            raw_response_excerpt=fallback.execution_metadata.raw_response_excerpt if fallback.execution_metadata else "",
                            stage_exit_code=getattr(exc, "exit_code", None),
                            stage_stdout=str(getattr(exc, "stdout", "") or ""),
                            stage_stderr=str(getattr(exc, "stderr", "") or ""),
                            stage_exception=f"{exc.__class__.__name__}: {exc}",
                            stage_returned_value=str(getattr(exc, "returned_value", "") or ""),
                        ),
                    )
            if not self.config.openclaw_agent_fallback_enabled:
                return EngineeringResult(
                    issue=issue,
                    repository=issue.repository,
                    patch_summary="OpenClaw Agent mode is unavailable and infer fallback is disabled.",
                    files_modified=(),
                    tests_executed=(),
                    test_results=(),
                    confidence=0.0,
                    errors=(capability.reason,),
                    engineering_notes=("mode=agent", "fallback=disabled"),
                    recommended_next_step="escalate",
                    execution_metadata=ExecutionMetadata(
                        mode="agent",
                        selected_reason="Agent mode is the required primary execution engine.",
                        command=capability.command,
                        subprocess=capability.command,
                        fallback_reason=capability.reason,
                    ),
                )
            fallback = self._run_infer_pipeline(repository_path=repository_path, issue=issue, dry_run=dry_run, run_tests=run_tests)
            return EngineeringResult(
                issue=fallback.issue,
                repository=fallback.repository,
                patch_summary=fallback.patch_summary,
                files_modified=fallback.files_modified,
                tests_executed=fallback.tests_executed,
                test_results=fallback.test_results,
                confidence=fallback.confidence,
                warnings=(*fallback.warnings, f"OpenClaw Agent mode unavailable: {capability.reason}", "Fell back to infer mode for this attempt."),
                errors=fallback.errors,
                engineering_notes=(*fallback.engineering_notes, "mode=infer_fallback"),
                recommended_next_step=fallback.recommended_next_step,
                verification=fallback.verification,
                execution_metadata=ExecutionMetadata(
                    mode="infer",
                    selected_reason="Infer mode was used only because Agent mode was unavailable.",
                    command=fallback.execution_metadata.command if fallback.execution_metadata else (),
                    subprocess=fallback.execution_metadata.subprocess if fallback.execution_metadata else (),
                    fallback_reason=capability.reason,
                    raw_response_excerpt=fallback.execution_metadata.raw_response_excerpt if fallback.execution_metadata else "",
                ),
            )
        return self._run_infer_pipeline(repository_path=repository_path, issue=issue, dry_run=dry_run, run_tests=run_tests)

    def _run_infer_pipeline(
        self,
        *,
        repository_path: Path,
        issue: EngineeringIssue,
        dry_run: bool,
        run_tests: bool,
    ) -> EngineeringResult:
        candidates = self.searcher.search(repository_path, issue)
        context = self.context_builder.build(repository_path=repository_path, issue=issue, candidates=candidates)
        if len(context.analysis.root_cause_evidence) < self.config.min_root_cause_evidence:
            return EngineeringResult(
                issue=issue,
                repository=issue.repository,
                patch_summary="Repository investigation did not produce enough evidence to safely patch.",
                files_modified=(),
                tests_executed=(),
                test_results=(),
                confidence=min(context.analysis.confidence, context.understanding.confidence),
                warnings=context.warnings,
                errors=("insufficient repository investigation evidence",),
                engineering_notes=(
                    f"issue_category={context.understanding.category}",
                    *context.analysis.root_cause_evidence,
                ),
                recommended_next_step="retry_with_better_context",
            )
        prompt = self.prompt_builder.build(context)
        provider = self.provider_factory.select()
        patch = provider.generate_patch(ProviderRequest(prompt=prompt))
        patch_validation = self.patch_validator.validate(repository_path, patch.unified_diff, context)
        repair_notes: list[str] = []
        for attempt in range(self.config.max_patch_repair_attempts):
            if patch_validation.valid:
                break
            failures = (*patch_validation.errors, *patch_validation.warnings)
            repair_notes.append(f"patch repair attempt {attempt + 1}: {'; '.join(failures)}")
            repair_prompt = self.prompt_builder.build_repair(
                context,
                previous_output=getattr(patch, "raw_text", "") or patch.unified_diff,
                failures=failures,
            )
            patch = provider.generate_patch(ProviderRequest(prompt=repair_prompt))
            patch_validation = self.patch_validator.validate(repository_path, patch.unified_diff, context)
        errors = list(patch_validation.errors)
        application = None
        if patch_validation.valid:
            application = self.patch_applier.apply(repository_path, patch.unified_diff, dry_run=dry_run)
            errors.extend(application.errors)
            if application.errors and not application.applied:
                for attempt in range(self.config.max_patch_repair_attempts):
                    failures = tuple(error for error in application.errors if error)
                    repair_notes.append(f"patch application repair attempt {attempt + 1}: {'; '.join(failures)}")
                    repair_prompt = self.prompt_builder.build_repair(
                        context,
                        previous_output=getattr(patch, "raw_text", "") or patch.unified_diff,
                        failures=failures,
                    )
                    patch = provider.generate_patch(ProviderRequest(prompt=repair_prompt))
                    patch_validation = self.patch_validator.validate(repository_path, patch.unified_diff, context)
                    if not patch_validation.valid:
                        errors = list(patch_validation.errors)
                        continue
                    application = self.patch_applier.apply(repository_path, patch.unified_diff, dry_run=dry_run)
                    errors = list(application.errors)
                    if application.applied:
                        break
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
            engineering_notes=(patch.reasoning_summary, f"provider={patch.provider_name}", f"dry_run={dry_run}", *repair_notes),
            recommended_next_step=recommended,
            execution_metadata=ExecutionMetadata(
                mode="infer",
                selected_reason="Infer mode was selected only within OpenClaw and uses the active OpenClaw default model.",
                selected_model=getattr(provider, "last_selected_model", None),
                selected_provider=getattr(provider, "last_selected_provider", None),
                command=tuple(getattr(provider, "last_command", ()) or ()),
                subprocess=tuple(getattr(provider, "subprocess_command", ()) or ()),
                raw_response_excerpt=getattr(patch, "raw_text", "")[:1000],
            ),
        )
