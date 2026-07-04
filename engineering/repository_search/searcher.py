"""Intelligent repository search and candidate ranking."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

from engineering.configuration import EngineeringConfiguration
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


@dataclass(slots=True)
class RepositorySearcher:
    """Searches by filename, symbol, class, function, keyword, and issue terms."""

    config: EngineeringConfiguration

    def search(self, repository_path: Path, issue: EngineeringIssue) -> tuple[CandidateFile, ...]:
        """Return ranked relevant files without reading the entire repository into memory."""

        terms = _issue_terms(issue)
        candidates: list[CandidateFile] = []
        for path in self._iter_files(repository_path):
            score = 0.0
            reasons: list[str] = []
            rel = path.relative_to(repository_path)
            name = rel.as_posix().lower()
            if any(term in name for term in terms):
                score += 8.0
                reasons.append("filename")
            text = self._read_sample(path)
            lower = text.lower()
            keyword_hits = sum(1 for term in terms if term in lower)
            if keyword_hits:
                score += min(keyword_hits * 3.0, 18.0)
                reasons.append("keyword")
            symbols = self._symbols(path, text)
            symbol_hits = tuple(symbol for symbol in symbols if any(term in symbol.lower() for term in terms))
            if symbol_hits:
                score += 10.0 + len(symbol_hits)
                reasons.append("symbol")
            if path.name in {"README", "README.md", "pyproject.toml", "package.json", "Cargo.toml", "go.mod"}:
                score += 1.5
                reasons.append("metadata")
            if score > 0:
                candidates.append(CandidateFile(path=path, score=score, reasons=tuple(dict.fromkeys(reasons)), symbols=symbol_hits))
        ranked = sorted(candidates, key=lambda item: (-item.score, len(item.path.parts), item.path.as_posix()))
        return tuple(ranked[: self.config.max_candidate_files])

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
