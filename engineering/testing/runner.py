"""Automatic project test detection and execution."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from engineering.configuration import EngineeringConfiguration
from engineering.models import TestCommand, TestResult


@dataclass(slots=True)
class TestRuntime:
    """Detects common project types and runs their test commands."""

    config: EngineeringConfiguration

    def detect(self, repository_path: Path) -> tuple[TestCommand, ...]:
        commands: list[TestCommand] = []
        if (repository_path / "pyproject.toml").exists() or (repository_path / "pytest.ini").exists():
            commands.append(TestCommand(("python", "-m", "pytest"), "Python project metadata detected"))
        if any(repository_path.glob("test*.py")):
            commands.append(TestCommand(("python", "-m", "unittest", "discover"), "unittest-style tests detected"))
        package_json = repository_path / "package.json"
        if package_json.exists():
            manager = "npm"
            if (repository_path / "pnpm-lock.yaml").exists():
                manager = "pnpm"
            elif (repository_path / "yarn.lock").exists():
                manager = "yarn"
            if self._package_has_test(package_json):
                commands.append(TestCommand((manager, "test"), "package.json test script detected"))
        if (repository_path / "go.mod").exists():
            commands.append(TestCommand(("go", "test", "./..."), "Go module detected"))
        if (repository_path / "Cargo.toml").exists():
            commands.append(TestCommand(("cargo", "test"), "Cargo project detected"))
        if list(repository_path.glob("*.sln")) or list(repository_path.glob("*.csproj")):
            commands.append(TestCommand(("dotnet", "test"), ".NET project detected"))
        return tuple(commands)

    def run(self, repository_path: Path, commands: tuple[TestCommand, ...]) -> tuple[TestResult, ...]:
        results: list[TestResult] = []
        for command in commands:
            started = perf_counter()
            completed = subprocess.run(
                list(command.command),
                cwd=repository_path,
                capture_output=True,
                text=True,
                timeout=self.config.test_timeout_seconds,
            )
            results.append(
                TestResult(
                    command=command.command,
                    exit_code=completed.returncode,
                    duration_ms=int((perf_counter() - started) * 1000),
                    stdout=completed.stdout[-4000:],
                    stderr=completed.stderr[-4000:],
                    passed=completed.returncode == 0,
                )
            )
        return tuple(results)

    def _package_has_test(self, path: Path) -> bool:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        return "test" in data.get("scripts", {})
