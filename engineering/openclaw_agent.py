"""OpenClaw Agent-mode engineering executor."""

from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from engineering.configuration import EngineeringConfiguration
from engineering.models import EngineeringIssue
from engineering.models.core import EngineeringResult, ExecutionMetadata, TestCommand, TestResult
from engineering.providers.openclaw import _read_model_selection, _resolve_cli_command


class OpenClawAgentError(RuntimeError):
    """Raised when OpenClaw Agent mode cannot be used successfully."""

    def __init__(
        self,
        message: str,
        *,
        exit_code: int | None = None,
        stdout: str = "",
        stderr: str = "",
        returned_value: str = "",
    ) -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.returned_value = returned_value


@dataclass(frozen=True, slots=True)
class OpenClawAgentCapability:
    """Detected Agent-mode capability state."""

    installed: bool
    callable: bool
    configured: bool
    command: tuple[str, ...] = ()
    reason: str = ""


@dataclass(frozen=True, slots=True)
class OpenClawAgentCapabilityDetector:
    """Detect whether OpenClaw Agent mode is callable."""

    cli: str = "openclaw"
    timeout_seconds: int = 20

    def detect(self) -> OpenClawAgentCapability:
        command_prefix = _resolve_cli_command(self.cli)
        if command_prefix is None:
            return OpenClawAgentCapability(False, False, False, (), f"{self.cli!r} was not found on PATH")
        help_result = self._run([*command_prefix, "agent", "--help"])
        if help_result.returncode != 0:
            detail = help_result.stderr.strip() or help_result.stdout.strip() or f"exit code {help_result.returncode}"
            return OpenClawAgentCapability(True, False, False, tuple(command_prefix), f"OpenClaw agent help failed: {detail}")
        status_result = self._run([*command_prefix, "status"])
        if status_result.returncode != 0:
            detail = status_result.stderr.strip() or status_result.stdout.strip() or f"exit code {status_result.returncode}"
            return OpenClawAgentCapability(True, True, False, tuple(command_prefix), f"OpenClaw status failed: {detail}")
        configured = "Gateway" in status_result.stdout
        reason = "OpenClaw agent is callable and gateway-backed agent sessions are available" if configured else "OpenClaw agent is callable but gateway readiness could not be confirmed"
        return OpenClawAgentCapability(True, True, configured, tuple(command_prefix), reason)

    def _run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=self.timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            return subprocess.CompletedProcess(command, 124, exc.stdout or "", exc.stderr or "OpenClaw agent capability detection timed out")


@dataclass(frozen=True, slots=True)
class OpenClawAgentExecutor:
    """Run one autonomous engineering task through OpenClaw Agent mode."""

    config: EngineeringConfiguration

    def execute(self, *, repository_path: Path, issue: EngineeringIssue, run_tests: bool) -> EngineeringResult:
        command_prefix = _resolve_cli_command(self.config.openclaw_cli)
        if command_prefix is None:
            raise OpenClawAgentError(f"{self.config.openclaw_cli!r} was not found on PATH")
        prompt = self._prompt(issue=issue, repository_path=repository_path, run_tests=run_tests)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".md", delete=False) as handle:
            handle.write(prompt)
            message_path = Path(handle.name)
        try:
            selection = _read_model_selection(self.config.openclaw_cli, timeout_seconds=min(self.config.openclaw_timeout_seconds, 30))
            command = [*command_prefix, "agent", "--agent", self.config.openclaw_agent_id, "--json", "--message-file", str(message_path)]
            if selection.resolved_model:
                command.extend(("--model", selection.resolved_model))
            if self.config.openclaw_thinking:
                command.extend(("--thinking", self.config.openclaw_thinking))
            command.extend(("--timeout", str(self.config.openclaw_timeout_seconds)))
            result = self._run(command, cwd=repository_path)
        finally:
            try:
                message_path.unlink(missing_ok=True)
            except OSError:
                pass
        files_modified = self._git_modified_files(repository_path)
        parsed = self._parse_response(result)
        execution_trace = parsed.get("result", {}).get("executionTrace", {})
        reply = self._reply_text(parsed)
        payload = _extract_json_payload(reply)
        test_results = _parse_test_results(payload.get("tests", ()))
        tests_executed = tuple(TestCommand(command=item.command, reason="OpenClaw agent executed this command") for item in test_results)
        warnings = tuple(str(item) for item in payload.get("warnings", ()))
        limitations = tuple(str(item) for item in payload.get("remaining_limitations", ()))
        engineering_notes = (
            f"mode=agent",
            f"agent_id={self.config.openclaw_agent_id}",
            f"selected_model={selection.resolved_model or 'unknown'}",
            f"selected_provider={selection.selected_provider or 'unknown'}",
            f"runner={execution_trace.get('runner', 'unknown')}",
            f"winner_provider={execution_trace.get('winnerProvider', 'unknown')}",
            *limitations,
        )
        return EngineeringResult(
            issue=issue,
            repository=issue.repository,
            patch_summary=str(payload.get("summary") or "OpenClaw agent completed the engineering task."),
            files_modified=files_modified,
            tests_executed=tests_executed,
            test_results=test_results,
            confidence=float(payload.get("confidence", 0.75)),
            warnings=warnings,
            errors=tuple(str(item) for item in payload.get("errors", ())),
            engineering_notes=engineering_notes,
            recommended_next_step=str(payload.get("recommended_next_step") or "review"),
            execution_metadata=ExecutionMetadata(
                mode="agent",
                selected_reason="OpenClaw Agent mode is installed, gateway-backed, and uses the active OpenClaw default model.",
                selected_model=selection.resolved_model,
                selected_provider=selection.selected_provider,
                command=tuple(command),
                subprocess=tuple(command_prefix),
                raw_response_excerpt=reply[:1000],
                stage_exit_code=result.returncode,
                stage_stdout=result.stdout or "",
                stage_stderr=result.stderr or "",
                stage_returned_value=reply[:4000],
            ),
        )

    def _run(self, command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                command,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.config.openclaw_timeout_seconds + 30,
            )
        except subprocess.TimeoutExpired as exc:
            raise OpenClawAgentError(
                f"OpenClaw agent timed out after {self.config.openclaw_timeout_seconds}s",
                exit_code=124,
                stdout=exc.stdout or "",
                stderr=exc.stderr or "",
            ) from exc
        except OSError as exc:
            raise OpenClawAgentError(f"OpenClaw agent failed to start: {exc}") from exc

    def _parse_response(self, result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        if result.returncode != 0:
            detail = stderr.strip() or stdout.strip() or f"exit code {result.returncode}"
            raise OpenClawAgentError(
                f"OpenClaw agent failed: {detail}",
                exit_code=result.returncode,
                stdout=stdout,
                stderr=stderr,
                returned_value=stdout[:4000],
            )
        if not stdout.strip():
            detail = stderr.strip()
            if detail:
                raise OpenClawAgentError(
                    f"OpenClaw agent returned no JSON on stdout: {detail}",
                    exit_code=result.returncode,
                    stdout=stdout,
                    stderr=stderr,
                )
            raise OpenClawAgentError(
                "OpenClaw agent returned no JSON on stdout",
                exit_code=result.returncode,
                stdout=stdout,
                stderr=stderr,
            )
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as exc:
            start = stdout.find("{")
            end = stdout.rfind("}")
            if start < 0 or end <= start:
                raise OpenClawAgentError(
                    f"OpenClaw agent returned invalid JSON: {exc}",
                    exit_code=result.returncode,
                    stdout=stdout,
                    stderr=stderr,
                    returned_value=stdout[:4000],
                ) from exc
            try:
                data = json.loads(stdout[start : end + 1])
            except json.JSONDecodeError as inner:
                raise OpenClawAgentError(
                    f"OpenClaw agent returned invalid JSON: {inner}",
                    exit_code=result.returncode,
                    stdout=stdout,
                    stderr=stderr,
                    returned_value=stdout[:4000],
                ) from inner
        if not isinstance(data, dict):
            raise OpenClawAgentError(
                "OpenClaw agent response was not a JSON object",
                exit_code=result.returncode,
                stdout=stdout,
                stderr=stderr,
                returned_value=stdout[:4000],
            )
        if str(data.get("status")) != "ok":
            raise OpenClawAgentError(
                str(data.get("summary") or data.get("error") or "OpenClaw agent failed"),
                exit_code=result.returncode,
                stdout=stdout,
                stderr=stderr,
                returned_value=stdout[:4000],
            )
        return data

    def _reply_text(self, data: dict[str, Any]) -> str:
        result = data.get("result", {})
        if not isinstance(result, dict):
            return ""
        direct = result.get("finalAssistantRawText") or result.get("finalAssistantVisibleText")
        if isinstance(direct, str) and direct.strip():
            return direct
        payloads = result.get("payloads")
        if not isinstance(payloads, list):
            return ""
        texts = [str(item.get("text")) for item in payloads if isinstance(item, dict) and item.get("text")]
        return "\n".join(texts)

    def _git_modified_files(self, repository_path: Path) -> tuple[str, ...]:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(repository_path),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
        if result.returncode != 0:
            return ()
        files: list[str] = []
        for line in result.stdout.splitlines():
            if len(line) < 4:
                continue
            path = line[3:].strip()
            if path:
                files.append(path)
        return tuple(dict.fromkeys(files))

    def _prompt(self, *, issue: EngineeringIssue, repository_path: Path, run_tests: bool) -> str:
        test_instruction = (
            "Validation is optional. Do not block completion on builds, tests, browser checks, localhost access, or application URLs."
            if not run_tests
            else "Validation is optional. You may run targeted checks if useful, but do not treat builds, tests, browser checks, localhost access, or application URLs as required gates."
        )
        return (
            "You are the software engineer for this Git repository.\n\n"
            f"Repository path: {repository_path}\n"
            f"Issue: {issue.repository}#{issue.number} - {issue.title}\n\n"
            "Requirements:\n"
            "- Investigate the repository yourself. Do not ask the caller to choose files.\n"
            "- Inspect any files, symbols, imports, tests, configs, and dependencies you need.\n"
            "- Modify source files directly in this repository when needed.\n"
            f"- {test_instruction}\n"
            "- Do not commit, push, or open a pull request.\n"
            "- If you cannot determine a fix, explain that clearly in the errors field.\n"
            "- When you finish, reply with JSON only using this schema:\n"
            "{\n"
            '  "summary": string,\n'
            '  "confidence": number,\n'
            '  "tests": [{"command": [string], "exit_code": number, "passed": boolean, "stdout": string, "stderr": string}],\n'
            '  "warnings": [string],\n'
            '  "errors": [string],\n'
            '  "remaining_limitations": [string],\n'
            '  "recommended_next_step": string\n'
            "}\n\n"
            f"Issue body:\n{issue.body or '(no issue body provided)'}\n"
        )


def _extract_json_payload(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        parts = stripped.split("```")
        for block in parts:
            block = block.strip()
            if block.startswith("json"):
                block = block[4:].strip()
            if block.startswith("{") and block.endswith("}"):
                stripped = block
                break
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise OpenClawAgentError(f"OpenClaw agent reply did not contain valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise OpenClawAgentError("OpenClaw agent reply JSON was not an object")
    return data


def _parse_test_results(items: Any) -> tuple[TestResult, ...]:
    results: list[TestResult] = []
    if not isinstance(items, list):
        return ()
    for item in items:
        if not isinstance(item, dict):
            continue
        command = item.get("command", ())
        if isinstance(command, str):
            command = (command,)
        elif isinstance(command, list):
            command = tuple(str(part) for part in command)
        else:
            command = ()
        results.append(
            TestResult(
                command=tuple(command),
                exit_code=int(item.get("exit_code", 0)),
                duration_ms=int(item.get("duration_ms", 0)),
                stdout=str(item.get("stdout", "")),
                stderr=str(item.get("stderr", "")),
                passed=bool(item.get("passed", False)),
            )
        )
    return tuple(results)
