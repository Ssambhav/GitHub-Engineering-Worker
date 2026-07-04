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
            "Issue": f"{issue.repository}#{issue.number}\nTitle: {issue.title}\nBody: {issue.body or ''}",
            "Repository Analysis": (
                f"{context.analysis.summary}\nAffected: {', '.join(context.analysis.affected_components)}\n"
                f"Possible root cause: {context.analysis.possible_root_cause}\n"
                f"Dependencies: {context.analysis.dependency_summary}"
            ),
            "Relevant Files": files,
            "Constraints": "Return a minimal repository-independent fix. Do not include prose inside the diff.",
        }
        return Prompt(
            system="You are an autonomous senior software engineer generating safe, minimal patches.",
            instructions=(
                "Use only the provided repository context.",
                "Produce a valid unified diff that applies from the repository root.",
                "Avoid unrelated refactors and generated/vendor/build files.",
            ),
            context_sections=sections,
            desired_output_format=(
                "Engineering Summary:\n<summary>\n\nConfidence: <0-1>\n\nModified Files:\n- <path>\n\n"
                "Reasoning Summary:\n<brief reasoning>\n\nUnified Diff:\n```diff\n<diff>\n```"
            ),
        )
