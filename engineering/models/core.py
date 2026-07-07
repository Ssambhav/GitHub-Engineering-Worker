"""Dataclasses exchanged by the engineering execution pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True, slots=True)
class EngineeringIssue:
    """Normalized issue input for code generation."""

    repository: str
    number: int
    title: str
    body: str | None = None
    labels: tuple[str, ...] = ()
    url: str | None = None


@dataclass(frozen=True, slots=True)
class IssueUnderstanding:
    """Structured issue understanding extracted before repository search."""

    category: str
    problem: str
    expected_behavior: str
    actual_behavior: str
    acceptance_criteria: tuple[str, ...]
    search_terms: tuple[str, ...]
    confidence: float


@dataclass(frozen=True, slots=True)
class CandidateFile:
    """Ranked repository file candidate."""

    path: Path
    score: float
    reasons: tuple[str, ...]
    symbols: tuple[str, ...] = ()
    category_hits: tuple[str, ...] = ()
    search_passes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FileSnippet:
    """Bounded file content included in model context."""

    path: Path
    content: str
    start_line: int
    end_line: int
    truncated: bool = False


@dataclass(frozen=True, slots=True)
class RepositoryAnalysis:
    """Structured repository analysis used for prompting and review."""

    issue_category: str
    summary: str
    affected_components: tuple[str, ...]
    possible_root_cause: str
    root_cause_evidence: tuple[str, ...]
    related_modules: tuple[str, ...]
    dependency_summary: str
    investigation_queries: tuple[str, ...]
    irrelevant_files: tuple[str, ...]
    files_safe_to_modify: tuple[str, ...]
    confidence: float


@dataclass(frozen=True, slots=True)
class EngineeringContext:
    """Structured context sent to an AI provider."""

    issue: EngineeringIssue
    understanding: IssueUnderstanding
    repository_path: Path
    repository_summary: str
    candidates: tuple[CandidateFile, ...]
    snippets: tuple[FileSnippet, ...]
    analysis: RepositoryAnalysis
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Prompt:
    """Structured prompt object for coding models."""

    system: str
    instructions: tuple[str, ...]
    context_sections: Mapping[str, str]
    desired_output_format: str

    def render(self) -> str:
        """Render the prompt at the provider boundary."""

        sections = [self.system, "", *self.instructions, "", "Context:"]
        sections.extend(f"## {name}\n{content}" for name, content in self.context_sections.items())
        sections.append(f"Desired Output Format:\n{self.desired_output_format}")
        return "\n".join(sections)


@dataclass(frozen=True, slots=True)
class ProviderRequest:
    """Typed request sent to an AI provider."""

    prompt: Prompt
    model: str | None = None
    temperature: float = 0.0


@dataclass(frozen=True, slots=True)
class PatchResponse:
    """Structured patch response returned by providers."""

    unified_diff: str
    engineering_summary: str
    confidence: float
    modified_files: tuple[str, ...]
    reasoning_summary: str
    provider_name: str
    raw_text: str = ""


@dataclass(frozen=True, slots=True)
class ExecutionMetadata:
    """Execution-mode evidence captured for the worker report."""

    mode: str
    selected_reason: str
    selected_model: str | None = None
    selected_provider: str | None = None
    command: tuple[str, ...] = ()
    subprocess: tuple[str, ...] = ()
    fallback_reason: str | None = None
    raw_response_excerpt: str = ""
    stage_exit_code: int | None = None
    stage_stdout: str = ""
    stage_stderr: str = ""
    stage_exception: str | None = None
    stage_returned_value: str = ""


@dataclass(frozen=True, slots=True)
class PatchValidationResult:
    """Patch validation outcome."""

    valid: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    modified_files: tuple[str, ...] = ()
    additions: int = 0
    deletions: int = 0
    rejected_files: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PatchApplicationResult:
    """Patch application outcome."""

    applied: bool
    dry_run: bool
    modified_files: tuple[str, ...]
    backups: tuple[Path, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TestCommand:
    """Detected test command."""

    command: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class TestResult:
    """Structured test execution result."""

    command: tuple[str, ...]
    exit_code: int
    duration_ms: int
    stdout: str
    stderr: str
    passed: bool


@dataclass(frozen=True, slots=True)
class VerificationAction:
    """One executed verification step."""

    action: str
    success: bool
    url: str = ""
    page_title: str = ""
    details: str = ""
    screenshot_paths: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Structured browser verification outcome."""

    attempted: bool
    passed: bool
    summary: str
    target_url: str | None = None
    issue_reproduced: bool = False
    expected_behavior_verified: bool = False
    visible_text_excerpt: str = ""
    screenshot_paths: tuple[str, ...] = ()
    actions: tuple[VerificationAction, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EngineeringResult:
    """Final result returned by the execution pipeline."""

    issue: EngineeringIssue
    repository: str
    patch_summary: str
    files_modified: tuple[str, ...]
    tests_executed: tuple[TestCommand, ...]
    test_results: tuple[TestResult, ...]
    confidence: float
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    engineering_notes: tuple[str, ...] = ()
    recommended_next_step: str = "review"
    verification: VerificationResult | None = None
    execution_metadata: ExecutionMetadata | None = None
