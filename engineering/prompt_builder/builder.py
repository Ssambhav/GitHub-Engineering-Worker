"""Reusable structured prompt builder."""

from __future__ import annotations

from dataclasses import dataclass

from engineering.models import EngineeringContext, Prompt


@dataclass(frozen=True, slots=True)
class PromptBuilder:
    """Builds coding model prompts from typed context."""

    def build(self, context: EngineeringContext) -> Prompt:
        """Construct a prompt requesting only a unified diff and summaries."""

        issue = context.issue
        files = "\n\n".join(
            f"### {snippet.path.relative_to(context.repository_path)}\n```text\n{snippet.content}\n```"
            for snippet in context.snippets
        )
        sections = {
            "Issue": (
                f"{issue.repository}#{issue.number}\nTitle: {issue.title}\nBody: {issue.body or ''}\n"
                f"Category: {context.understanding.category}\nProblem: {context.understanding.problem}\n"
                f"Expected: {context.understanding.expected_behavior}\nActual: {context.understanding.actual_behavior}\n"
                f"Acceptance Criteria:\n- " + "\n- ".join(context.understanding.acceptance_criteria)
            ),
            "Repository Analysis": (
                f"{context.analysis.summary}\nAffected: {', '.join(context.analysis.affected_components)}\n"
                f"Possible root cause: {context.analysis.possible_root_cause}\n"
                f"Root cause evidence:\n- " + ("\n- ".join(context.analysis.root_cause_evidence) if context.analysis.root_cause_evidence else "Need more evidence before patching.")
                + f"\nInvestigation passes: {', '.join(context.analysis.investigation_queries)}\n"
                f"Safe files to modify: {', '.join(context.analysis.files_safe_to_modify)}\n"
                f"Do not modify: {', '.join(context.analysis.irrelevant_files) if context.analysis.irrelevant_files else 'unrelated files not in current context'}\n"
                f"Dependencies: {context.analysis.dependency_summary}"
            ),
            "Relevant Files": files,
            "Constraints": (
                "Return a minimal repository-independent fix. Do not include prose inside the diff.\n"
                "Modify only files supported by the investigation evidence.\n"
                "If root cause evidence is weak, refuse to guess and explain what additional code context is required."
            ),
        }
        return Prompt(
            system="You are an autonomous senior software engineer generating safe, minimal patches.",
            instructions=(
                "Use only the provided repository context.",
                "Do not patch documentation for non-documentation issues.",
                "Produce a valid unified diff that applies from the repository root.",
                "Avoid unrelated refactors and generated/vendor/build files.",
            ),
            context_sections=sections,
            desired_output_format=(
                "Engineering Summary:\n<summary>\n\nConfidence: <0-1>\n\nModified Files:\n- <path>\n\n"
                "Reasoning Summary:\n<brief reasoning>\n\nUnified Diff:\n```diff\n<diff>\n```"
            ),
        )

    def build_repair(self, context: EngineeringContext, *, previous_output: str, failures: tuple[str, ...]) -> Prompt:
        """Construct a bounded corrective prompt after invalid provider output."""

        issue = context.issue
        files = "\n\n".join(
            f"### {snippet.path.relative_to(context.repository_path)}\n```text\n{snippet.content[:4000]}\n```"
            for snippet in context.snippets[:3]
        )
        sections = {
            "Issue": (
                f"{issue.repository}#{issue.number}\nTitle: {issue.title}\nBody: {issue.body or ''}\n"
                f"Category: {context.understanding.category}"
            ),
            "Validation Failure": "\n".join(f"- {failure}" for failure in failures),
            "Previous Invalid Output": previous_output[:6000],
            "Relevant Files": files,
            "Required Correction": (
                "Return a valid unified diff only inside the requested response shape. "
                "The diff must apply from the repository root and include ---/+++/@@ hunks. "
                "Do not introduce unrelated files or documentation edits for non-documentation issues."
            ),
        }
        return Prompt(
            system="You repair invalid patch output for an autonomous engineering worker.",
            instructions=(
                "Do not repeat the invalid format.",
                "Do not include markdown prose inside the diff block.",
                "If no code change is possible from the provided context, return an empty Unified Diff and explain why in Reasoning Summary.",
            ),
            context_sections=sections,
            desired_output_format=(
                "Engineering Summary:\n<summary>\n\nConfidence: <0-1>\n\nModified Files:\n- <path>\n\n"
                "Reasoning Summary:\n<brief reasoning>\n\nUnified Diff:\n```diff\n<valid unified diff>\n```"
            ),
        )
