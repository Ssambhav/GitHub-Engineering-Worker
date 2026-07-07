"""Structured repository analysis."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from engineering.issue_understanding import understand_issue
from engineering.models import CandidateFile, EngineeringIssue, RepositoryAnalysis


@dataclass(frozen=True, slots=True)
class RepositoryAnalyzer:
    """Produces a bounded, evidence-based repository analysis."""

    def analyze(self, repository_path: Path, issue: EngineeringIssue, candidates: tuple[CandidateFile, ...]) -> RepositoryAnalysis:
        understanding = understand_issue(issue)
        components = tuple(dict.fromkeys(_component(repository_path, item.path) for item in candidates[:6]))
        manifests = [name for name in ("pyproject.toml", "package.json", "go.mod", "Cargo.toml", "*.csproj") if list(repository_path.glob(name))]
        summary = f"Repository {issue.repository} classified as {understanding.category} with {len(candidates)} ranked candidate files."
        dependency = f"Detected manifests: {', '.join(manifests) if manifests else 'none from supported set'}."
        evidence_entries: list[str] = []
        for item in candidates:
            rel = item.path.relative_to(repository_path)
            if len(item.search_passes) >= 2:
                evidence_entries.append(f"{rel} matched multiple search passes: {', '.join(item.search_passes)}")
            if "symbol" in item.reasons and item.symbols:
                evidence_entries.append(f"{rel} matched symbols: {', '.join(item.symbols[:4])}")
            if "category_path" in item.reasons and item.category_hits:
                evidence_entries.append(f"{rel} matched category paths: {', '.join(item.category_hits[:4])}")
            if "keyword" in item.reasons and "filename" in item.reasons:
                evidence_entries.append(f"{rel} matched both filename and content terms")
        evidence = tuple(dict.fromkeys(evidence_entries))[:6]
        related_modules = tuple(str(item.path.relative_to(repository_path)) for item in candidates[:6])
        safe_to_modify = tuple(str(item.path.relative_to(repository_path)) for item in candidates[:4])
        irrelevant = tuple(
            str(item.path.relative_to(repository_path))
            for item in candidates
            if item.path.name.lower().endswith(".md") and understanding.category != "Documentation"
        )[:4]
        root_cause = (
            f"Likely related to {components[0]} because multiple repository signals converged on {safe_to_modify[0]}."
            if components and safe_to_modify
            else "Insufficient repository matches to identify a likely root cause."
        )
        confidence = min(0.92, 0.25 + (len(evidence) * 0.14) + (0.08 if safe_to_modify else 0.0))
        return RepositoryAnalysis(
            issue_category=understanding.category,
            summary=summary,
            affected_components=components,
            possible_root_cause=root_cause,
            root_cause_evidence=evidence,
            related_modules=related_modules,
            dependency_summary=dependency,
            investigation_queries=tuple(dict.fromkeys(pass_name for item in candidates for pass_name in item.search_passes)),
            irrelevant_files=irrelevant,
            files_safe_to_modify=safe_to_modify,
            confidence=confidence,
        )


def _component(root: Path, path: Path) -> str:
    rel = path.relative_to(root)
    return rel.parts[0] if len(rel.parts) > 1 else rel.name
