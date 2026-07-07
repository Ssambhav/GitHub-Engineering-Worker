"""Build structured, size-limited engineering context."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from engineering.analysis import RepositoryAnalyzer
from engineering.configuration import EngineeringConfiguration
from engineering.issue_understanding import understand_issue
from engineering.models import CandidateFile, EngineeringContext, EngineeringIssue, FileSnippet


@dataclass(slots=True)
class ContextBuilder:
    """Reads only ranked relevant files and respects configured byte limits."""

    config: EngineeringConfiguration
    analyzer: RepositoryAnalyzer

    def build(
        self,
        *,
        repository_path: Path,
        issue: EngineeringIssue,
        candidates: tuple[CandidateFile, ...],
    ) -> EngineeringContext:
        snippets: list[FileSnippet] = []
        warnings: list[str] = []
        remaining = self.config.max_context_bytes
        understanding = understand_issue(issue)
        relevant_candidates = self._prioritized_candidates(candidates, understanding.category)
        for candidate in relevant_candidates[: self.config.max_files_to_read]:
            if remaining <= 0:
                warnings.append("context byte limit reached")
                break
            try:
                raw = candidate.path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                warnings.append(f"unable to read {candidate.path}: {exc}")
                continue
            bounded = raw[: min(self.config.max_file_bytes, remaining)]
            remaining -= len(bounded.encode("utf-8", errors="replace"))
            line_count = bounded.count("\n") + (1 if bounded else 0)
            snippets.append(
                FileSnippet(
                    path=candidate.path,
                    content=bounded,
                    start_line=1,
                    end_line=line_count,
                    truncated=len(bounded) < len(raw),
                )
            )
        analysis = self.analyzer.analyze(repository_path, issue, candidates)
        if len(analysis.root_cause_evidence) < self.config.min_root_cause_evidence:
            warnings.append("insufficient root cause evidence; continue repository investigation before patch generation")
        return EngineeringContext(
            issue=issue,
            understanding=understanding,
            repository_path=repository_path,
            repository_summary=analysis.summary,
            candidates=candidates,
            snippets=tuple(snippets),
            analysis=analysis,
            warnings=tuple(warnings),
        )

    def _prioritized_candidates(self, candidates: tuple[CandidateFile, ...], category: str) -> tuple[CandidateFile, ...]:
        prioritized = sorted(
            candidates,
            key=lambda item: (
                item.path.name.lower().endswith(".md") and category != "Documentation",
                -len(item.search_passes),
                0 if "symbol" in item.reasons else 1,
                -item.score,
            ),
        )
        return tuple(prioritized)
