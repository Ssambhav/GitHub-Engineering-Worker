"""Intelligent repository search and candidate ranking."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

from engineering.configuration import EngineeringConfiguration
from engineering.issue_understanding import understand_issue
from engineering.models import CandidateFile, EngineeringIssue

IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    "node_modules",
    "vendor",
    "dist",
    "build",
    ".next",
    ".venv",
    "venv",
    "target",
    "coverage",
}
GENERATED_SUFFIXES = (".min.js", ".map", ".lock")
TEXT_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".go",
    ".rs",
    ".java",
    ".cs",
    ".rb",
    ".php",
    ".md",
    ".txt",
    "",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".html",
    ".css",
}
NON_ENGINEERING_FILES = {"readme", "readme.md", "contributing.md", "code_of_conduct.md", "license", "security.md"}
CATEGORY_PATH_HINTS: dict[str, tuple[str, ...]] = {
    "Frontend UI": ("ui", "frontend", "components", "pages", "app", "styles", "css", "theme"),
    "Backend": ("backend", "server", "worker", "services", "runtime", "execution"),
    "API": ("api", "routes", "controllers", "client", "http"),
    "Business Logic": ("engineering", "decision", "planner", "reasoning", "worker"),
    "Validation": ("validation", "validators", "schemas", "contracts"),
    "Database": ("database", "db", "migrations", "models", "repositories"),
    "Authentication": ("auth", "authentication", "security", "credentials"),
    "Performance": ("performance", "cache", "runtime", "scheduler"),
    "Documentation": ("docs", "readme", "examples"),
    "Configuration": ("configuration", "config", "settings", "sample-config"),
    "Testing": ("tests", "testing", "spec"),
    "Build/CI": (".github", "workflow", "build", "ci"),
}


@dataclass(slots=True)
class RepositorySearcher:
    """Searches by filename, symbol, class, function, keyword, and issue terms."""

    config: EngineeringConfiguration

    def search(self, repository_path: Path, issue: EngineeringIssue) -> tuple[CandidateFile, ...]:
        """Return ranked relevant files without reading the entire repository into memory."""

        understanding = understand_issue(issue)
        search_plans = self._search_plans(issue, understanding.search_terms, understanding.category)
        candidates_by_path: dict[Path, CandidateFile] = {}
        for path in self._iter_files(repository_path):
            text = self._read_sample(path)
            symbols = self._symbols(path, text)
            for plan_name, terms in search_plans:
                candidate = self._score_candidate(repository_path, path, text, symbols, terms, understanding.category, plan_name)
                if candidate is None:
                    continue
                existing = candidates_by_path.get(path)
                if existing is None:
                    candidates_by_path[path] = candidate
                else:
                    candidates_by_path[path] = CandidateFile(
                        path=path,
                        score=existing.score + candidate.score,
                        reasons=tuple(dict.fromkeys((*existing.reasons, *candidate.reasons))),
                        symbols=tuple(dict.fromkeys((*existing.symbols, *candidate.symbols))),
                        category_hits=tuple(dict.fromkeys((*existing.category_hits, *candidate.category_hits))),
                        search_passes=tuple(dict.fromkeys((*existing.search_passes, *candidate.search_passes))),
                    )
        ranked = sorted(candidates_by_path.values(), key=lambda item: (-item.score, len(item.path.parts), item.path.as_posix()))
        return tuple(ranked[: max(self.config.max_candidate_files, self.config.min_candidate_files)])

    def _score_candidate(
        self,
        repository_path: Path,
        path: Path,
        text: str,
        symbols: tuple[str, ...],
        terms: tuple[str, ...],
        category: str,
        plan_name: str,
    ) -> CandidateFile | None:
        score = 0.0
        reasons: list[str] = []
        rel = path.relative_to(repository_path)
        name = rel.as_posix().lower()
        lower = text.lower()
        symbol_hits = tuple(symbol for symbol in symbols if any(term in symbol.lower() for term in terms))
        filename_hits = sum(1 for term in terms if term in name)
        keyword_hits = sum(1 for term in terms if term in lower)
        path_hits = [hint for hint in CATEGORY_PATH_HINTS.get(category, ()) if hint in name]
        if filename_hits:
            score += min(filename_hits * 6.0, 18.0)
            reasons.append("filename")
        if keyword_hits:
            score += min(keyword_hits * 2.5, 15.0)
            reasons.append("keyword")
        if symbol_hits:
            score += 10.0 + len(symbol_hits)
            reasons.append("symbol")
        if path_hits:
            score += min(len(path_hits) * 4.0, 12.0)
            reasons.append("category_path")
        if _is_test_file(path):
            score += 2.0
            reasons.append("test")
        if path.name.lower() in NON_ENGINEERING_FILES and category != "Documentation":
            score -= 12.0
            reasons.append("non_engineering_penalty")
        elif path.name in {"pyproject.toml", "package.json", "Cargo.toml", "go.mod"}:
            score += 1.5
            reasons.append("metadata")
        if score <= 0:
            return None
        return CandidateFile(
            path=path,
            score=score,
            reasons=tuple(dict.fromkeys(reasons)),
            symbols=symbol_hits,
            category_hits=tuple(dict.fromkeys(path_hits)),
            search_passes=(plan_name,),
        )

    def _search_plans(self, issue: EngineeringIssue, search_terms: tuple[str, ...], category: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
        issue_terms = _issue_terms(issue)
        category_terms = tuple(dict.fromkeys((*CATEGORY_PATH_HINTS.get(category, ()), *search_terms[:8])))
        title_terms = tuple(dict.fromkeys(issue_terms[:10]))
        symbol_terms = tuple(dict.fromkeys(term for term in (*search_terms, *issue_terms) if len(term) >= 4))[:12]
        return (
            ("title_terms", title_terms),
            ("category_terms", category_terms),
            ("symbol_terms", symbol_terms),
        )

    def _iter_files(self, repository_path: Path):
        for path in repository_path.rglob("*"):
            if not path.is_file():
                continue
            parts = set(path.relative_to(repository_path).parts)
            if parts & IGNORED_DIRS:
                continue
            if path.name.endswith(GENERATED_SUFFIXES) or path.suffix.lower() not in TEXT_EXTENSIONS:
                continue
            try:
                if b"\0" in path.read_bytes()[:2048]:
                    continue
            except OSError:
                continue
            yield path

    def _read_sample(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="replace")[: self.config.max_file_bytes]
        except OSError:
            return ""

    def _symbols(self, path: Path, text: str) -> tuple[str, ...]:
        if path.suffix == ".py":
            try:
                tree = ast.parse(text)
            except SyntaxError:
                return ()
            return tuple(
                node.name
                for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
            )
        pattern = re.compile(r"\b(?:class|function|def|const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)")
        return tuple(match.group(1) for match in pattern.finditer(text))


def _issue_terms(issue: EngineeringIssue) -> tuple[str, ...]:
    raw = f"{issue.title} {issue.body or ''} {' '.join(issue.labels)}"
    terms = [term.lower() for term in re.findall(r"[A-Za-z][A-Za-z0-9_]{2,}", raw)]
    stop = {"the", "and", "for", "with", "that", "this", "from", "issue", "bug", "fix", "error"}
    return tuple(dict.fromkeys(term for term in terms if term not in stop))[:24]


def _is_test_file(path: Path) -> bool:
    lowered = path.as_posix().lower()
    return "test" in lowered or "spec" in lowered
