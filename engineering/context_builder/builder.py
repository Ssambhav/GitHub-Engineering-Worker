"""Build structured, size-limited engineering context."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from engineering.analysis import RepositoryAnalyzer
from engineering.configuration import EngineeringConfiguration
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
        for candidate in candidates[: self.config.max_files_to_read]:
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
        return EngineeringContext(
            issue=issue,
            repository_path=repository_path,
            repository_summary=analysis.summary,
            candidates=candidates,
            snippets=tuple(snippets),
            analysis=analysis,
            warnings=tuple(warnings),
        )
