"""Structured repository analysis."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from engineering.models import CandidateFile, EngineeringIssue, RepositoryAnalysis


@dataclass(frozen=True, slots=True)
class RepositoryAnalyzer:
    """Produces a bounded, evidence-based repository analysis."""

    def analyze(self, repository_path: Path, issue: EngineeringIssue, candidates: tuple[CandidateFile, ...]) -> RepositoryAnalysis:
        components = tuple(dict.fromkeys(_component(repository_path, item.path) for item in candidates[:6]))
        manifests = [name for name in ("pyproject.toml", "package.json", "go.mod", "Cargo.toml", "*.csproj") if list(repository_path.glob(name))]
        summary = f"Repository {issue.repository} with {len(candidates)} ranked candidate files."
        dependency = f"Detected manifests: {', '.join(manifests) if manifests else 'none from supported set'}."
        root_cause = (
            f"Likely related to {components[0]} based on issue terms and ranked files."
            if components
            else "Insufficient repository matches to identify a likely root cause."
        )
        confidence = min(0.85, 0.35 + (len(candidates) * 0.05))
        return RepositoryAnalysis(
            summary=summary,
            affected_components=components,
            possible_root_cause=root_cause,
            related_modules=tuple(str(item.path.relative_to(repository_path)) for item in candidates[:6]),
            dependency_summary=dependency,
            confidence=confidence,
        )


def _component(root: Path, path: Path) -> str:
    rel = path.relative_to(root)
    return rel.parts[0] if len(rel.parts) > 1 else rel.name
