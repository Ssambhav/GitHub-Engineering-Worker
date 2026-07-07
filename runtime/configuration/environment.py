"""Environment bootstrap helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

_LOADED = False


def load_environment(*, start: Path | None = None, override: bool = False) -> Path | None:
    """Load a repository .env file into os.environ once.

    python-dotenv is used when installed. A small fallback parser keeps local
    CLI execution reliable before optional development dependencies are
    installed. Existing process environment values win by default.
    """

    global _LOADED
    if _LOADED and not override:
        return _find_env_file(start or Path.cwd())

    env_path = _find_env_file(start or Path.cwd())
    if env_path is None:
        _LOADED = True
        return None

    try:
        from dotenv import load_dotenv

        load_dotenv(env_path, override=override)
    except ModuleNotFoundError:
        _load_env_fallback(env_path, override=override)

    _LOADED = True
    return env_path


def environment_with_dotenv(environment: Mapping[str, str] | None = None) -> Mapping[str, str]:
    """Return an environment mapping after loading .env for default process env."""

    if environment is None:
        load_environment()
        return os.environ
    return environment


def _find_env_file(start: Path) -> Path | None:
    candidates = [start.resolve(), *start.resolve().parents]
    package_root = Path(__file__).resolve().parents[2]
    candidates.extend([package_root, *package_root.parents])
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        env_path = candidate / ".env"
        if env_path.exists() and env_path.is_file():
            return env_path
    return None


def _load_env_fallback(path: Path, *, override: bool) -> None:
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        if not override and key in os.environ:
            continue
        os.environ[key] = _clean_value(value.strip())


def _clean_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value
