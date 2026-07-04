"""Shared filesystem helpers for local tools."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from tools.context import ToolContext
from tools.exceptions import ToolValidationException

BINARY_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".gz", ".exe", ".dll", ".pyc"}
DEFAULT_IGNORES = {".git", ".venv", "__pycache__", ".mypy_cache", ".pytest_cache", "node_modules"}


def resolve_workspace_path(context: ToolContext, value: str | Path) -> Path:
    root = context.configuration.workspace_root.resolve()
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    resolved = path.resolve()
    if resolved != root and root not in resolved.parents:
        raise ToolValidationException(f"path escapes workspace: {value}")
    return resolved


def detect_encoding(path: Path, default: str) -> str:
    sample = path.read_bytes()[:4096]
    if sample.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if b"\x00" in sample:
        raise ToolValidationException(f"binary file is not supported: {path}")
    for encoding in (default, "utf-8", "utf-16", "cp1252"):
        try:
            sample.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    return default


def ensure_readable_file(path: Path, context: ToolContext) -> None:
    if not path.exists() or not path.is_file():
        raise ToolValidationException(f"file not found: {path}")
    if path.suffix.lower() in BINARY_EXTENSIONS:
        raise ToolValidationException(f"unsupported file type: {path.suffix}")
    if path.stat().st_size > context.configuration.max_file_size_bytes:
        raise ToolValidationException(f"file exceeds size limit: {path}")


def ignored(path: Path, ignore_names: Iterable[str] = DEFAULT_IGNORES) -> bool:
    names = set(ignore_names)
    return any(part in names for part in path.parts)


def iter_files(root: Path, max_depth: int, extensions: set[str] | None = None) -> Iterable[Path]:
    base_depth = len(root.parts)
    for path in root.rglob("*"):
        if ignored(path):
            continue
        depth = len(path.parts) - base_depth
        if depth > max_depth:
            continue
        if path.is_file() and (extensions is None or path.suffix.lower() in extensions):
            yield path
