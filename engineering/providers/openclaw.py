"""OpenClaw CLI-backed AI provider."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any

from engineering.models.core import PatchResponse, ProviderRequest
from engineering.providers.parsers import parse_patch_response


class OpenClawProviderError(RuntimeError):
    """Raised when the supported OpenClaw inference surface fails."""


MAX_CLI_PROMPT_CHARS = 12_000
MAX_COMMAND_CHARS = 24_000


@dataclass(frozen=True, slots=True)
class OpenClawCapability:
    """Detected OpenClaw callable-interface state."""

    installed: bool
    callable: bool
    configured: bool
    interface: str | None
    command: str | None
    reason: str
    providers: tuple[str, ...] = ()
    selected_provider: str | None = None


@dataclass(frozen=True, slots=True)
class OpenClawModelSelection:
    """Resolved model selection from the active OpenClaw runtime config."""

    default_model: str | None
    resolved_model: str | None
    selected_provider: str | None
    config_path: str | None = None
    reason: str = ""


@dataclass(frozen=True, slots=True)
class OpenClawCapabilityDetector:
    """Detects supported OpenClaw inference capabilities."""

    cli: str = "openclaw"
    timeout_seconds: int = 20

    def detect(self) -> OpenClawCapability:
        command_prefix = _resolve_cli_command(self.cli)
        if command_prefix is None:
            return OpenClawCapability(False, False, False, None, None, f"{self.cli!r} was not found on PATH")
        executable = command_prefix[-1]

        help_result = self._run((*command_prefix, "infer", "model", "run", "--help"))
        if help_result.returncode != 0:
            detail = help_result.stderr.strip() or help_result.stdout.strip()
            return OpenClawCapability(True, False, False, None, executable, f"OpenClaw infer model run help failed: {detail}")

        providers_result = self._run((*command_prefix, "infer", "model", "providers", "--json"))
        interface = "cli:openclaw infer model run --json"
        if providers_result.returncode != 0:
            detail = providers_result.stderr.strip() or providers_result.stdout.strip()
            return OpenClawCapability(True, True, False, interface, executable, f"OpenClaw provider inspection failed: {detail}")

        try:
            provider_rows = json.loads(providers_result.stdout)
        except json.JSONDecodeError as exc:
            return OpenClawCapability(True, True, False, interface, executable, f"OpenClaw provider inspection returned invalid JSON: {exc}")

        configured = [row for row in provider_rows if bool(row.get("configured"))]
        selected = next((str(row.get("provider")) for row in provider_rows if bool(row.get("selected"))), None)
        provider_names = tuple(str(row.get("provider")) for row in provider_rows if row.get("provider"))
        if not configured:
            return OpenClawCapability(
                True,
                True,
                False,
                interface,
                executable,
                "OpenClaw is callable, but no model provider is configured",
                provider_names,
                selected,
            )
        return OpenClawCapability(
            True,
            True,
            True,
            interface,
            executable,
            "OpenClaw infer model run is available with configured provider auth",
            provider_names,
            selected,
        )

    def _run(self, command: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=self.timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            return subprocess.CompletedProcess(command, 124, exc.stdout or "", exc.stderr or "OpenClaw capability detection timed out")


@dataclass(frozen=True, slots=True)
class OpenClawProvider:
    """Provider that calls the supported OpenClaw headless inference CLI."""

    cli: str = "openclaw"
    model: str | None = None
    timeout_seconds: int = 180
    retries: int = 1
    thinking: str | None = None
    name: str = "openclaw"
    last_command: tuple[str, ...] = ()
    subprocess_command: tuple[str, ...] = ()
    last_selected_model: str | None = None
    last_selected_provider: str | None = None

    def infer_text(self, prompt: str) -> str:
        """Run a general OpenClaw inference request and return text output."""

        command_prefix = _resolve_cli_command(self.cli)
        if command_prefix is None:
            raise OpenClawProviderError(f"{self.cli!r} was not found on PATH")
        selection = self.model_selection()
        prompt = _bounded_prompt(prompt)
        command = [*command_prefix, "infer", "model", "run", "--prompt", prompt, "--json"]
        selected_model = self.model or selection.resolved_model
        if self.model:
            command.extend(("--model", self.model))
        if self.thinking:
            command.extend(("--thinking", self.thinking))
        object.__setattr__(self, "last_command", tuple(command))
        object.__setattr__(self, "subprocess_command", tuple(command_prefix))
        object.__setattr__(self, "last_selected_model", selected_model)
        object.__setattr__(self, "last_selected_provider", _provider_from_model(selected_model) or selection.selected_provider)

        last_error: str | None = None
        for _ in range(max(1, self.retries + 1)):
            try:
                return self._extract_text(self._run(command))
            except OpenClawProviderError as exc:
                last_error = str(exc)
        raise OpenClawProviderError(last_error or "OpenClaw provider failed without an error message")

    def generate_patch(self, request: ProviderRequest) -> PatchResponse:
        command_prefix = _resolve_cli_command(self.cli)
        if command_prefix is None:
            raise OpenClawProviderError(f"{self.cli!r} was not found on PATH")
        selection = self.model_selection()
        prompt = _bounded_prompt(request.prompt.render())
        command = [*command_prefix, "infer", "model", "run", "--prompt", prompt, "--json"]
        selected_model = request.model or self.model or selection.resolved_model
        if request.model or self.model:
            command.extend(("--model", selected_model))
        if self.thinking:
            command.extend(("--thinking", self.thinking))
        object.__setattr__(self, "last_command", tuple(command))
        object.__setattr__(self, "subprocess_command", tuple(command_prefix))
        object.__setattr__(self, "last_selected_model", selected_model)
        object.__setattr__(self, "last_selected_provider", _provider_from_model(selected_model) or selection.selected_provider)

        last_error: str | None = None
        for _ in range(max(1, self.retries + 1)):
            try:
                data = self._run(command)
                return parse_patch_response(self._extract_text(data), provider_name=self.name)
            except OpenClawProviderError as exc:
                last_error = str(exc)
        raise OpenClawProviderError(last_error or "OpenClaw provider failed without an error message")

    def health(self) -> OpenClawCapability:
        return OpenClawCapabilityDetector(self.cli, timeout_seconds=min(self.timeout_seconds, 30)).detect()

    def model_selection(self) -> OpenClawModelSelection:
        return _read_model_selection(self.cli, timeout_seconds=min(self.timeout_seconds, 30))

    def _run(self, command: list[str]) -> dict[str, Any]:
        _assert_command_safe(command)
        try:
            result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=self.timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            raise OpenClawProviderError(f"OpenClaw inference timed out after {self.timeout_seconds}s") from exc
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            raise OpenClawProviderError(f"OpenClaw inference failed to start: {exc}") from exc

        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
            raise OpenClawProviderError(f"OpenClaw inference failed: {detail}")
        data = _loads_json_envelope(result.stdout)
        if not data.get("ok", False):
            raise OpenClawProviderError(str(data.get("error") or "OpenClaw returned ok=false"))
        return data

    def _extract_text(self, data: dict[str, Any]) -> str:
        outputs = data.get("outputs")
        if not isinstance(outputs, list):
            raise OpenClawProviderError("OpenClaw response did not include an outputs array")
        texts = [str(item.get("text")) for item in outputs if isinstance(item, dict) and item.get("text")]
        if not texts:
            raise OpenClawProviderError("OpenClaw response did not include text output")
        return "\n\n".join(texts)


def _resolve_cli_command(cli: str) -> list[str] | None:
    if os.name == "nt":
        direct = shutil.which(cli)
        if direct:
            module = os.path.join(os.path.dirname(direct), "node_modules", "openclaw", "openclaw.mjs")
            node = shutil.which("node.exe") or shutil.which("node")
            if node and os.path.exists(module):
                return [node, module]
        for suffix in (".cmd", ".exe", ".bat"):
            candidate = shutil.which(cli + suffix)
            if candidate:
                return [candidate]
        ps1 = shutil.which(cli + ".ps1")
        if ps1:
            shell = shutil.which("pwsh") or shutil.which("powershell.exe") or shutil.which("powershell")
            if shell:
                return [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1]
    direct = shutil.which(cli)
    if direct and _is_launchable_path(direct):
        return [direct]
    return [direct] if direct else None


def _is_launchable_path(path: str) -> bool:
    if os.name != "nt":
        return True
    return path.lower().endswith((".exe", ".cmd", ".bat", ".com", ".ps1"))


def _loads_json_envelope(text: str) -> dict[str, Any]:
    if not text:
        raise OpenClawProviderError("OpenClaw did not return stdout JSON")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise OpenClawProviderError("OpenClaw did not return a JSON object")
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise OpenClawProviderError(f"OpenClaw returned invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise OpenClawProviderError("OpenClaw JSON response was not an object")
    return data


def _bounded_prompt(prompt: str, *, max_chars: int = MAX_CLI_PROMPT_CHARS) -> str:
    """Return a subprocess-safe prompt for OpenClaw's current --prompt-only model API."""

    if len(prompt) <= max_chars:
        return prompt
    sections = re.split(r"\n(?=##? |Desired Output Format:)", prompt)
    priority_names = (
        "issue",
        "task",
        "instructions",
        "acceptance",
        "repository",
        "files",
        "tests",
        "output",
        "validation failure",
        "previous invalid output",
        "required correction",
    )
    selected: list[str] = []
    for section in sections:
        heading = section.splitlines()[0].lower() if section.splitlines() else ""
        if any(name in heading for name in priority_names):
            selected.append(section)
    compacted = "\n\n".join(selected) if selected else prompt
    notice = "\n\n[Context compacted before OpenClaw invocation to keep subprocess transport below OS command-line limits.]\n\n"
    if len(compacted) > max_chars:
        head_budget = max_chars // 2
        tail_budget = max_chars - head_budget - len(notice)
        compacted = (
            compacted[:head_budget]
            + notice
            + compacted[-tail_budget:]
        )
    return compacted


def _assert_command_safe(command: list[str]) -> None:
    total = sum(len(part) + 1 for part in command)
    if total > MAX_COMMAND_CHARS:
        raise OpenClawProviderError(
            f"refusing unsafe OpenClaw invocation: command length {total} exceeds {MAX_COMMAND_CHARS}; prompt bounding failed"
        )


def _read_model_selection(cli: str, *, timeout_seconds: int) -> OpenClawModelSelection:
    command_prefix = _resolve_cli_command(cli)
    if command_prefix is None:
        raise OpenClawProviderError(f"{cli!r} was not found on PATH")
    try:
        result = subprocess.run(
            [*command_prefix, "models", "status", "--json"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise OpenClawProviderError("OpenClaw model status timed out") from exc
    except Exception as exc:
        raise OpenClawProviderError(f"OpenClaw model status failed to start: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
        raise OpenClawProviderError(f"OpenClaw model status failed: {detail}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise OpenClawProviderError(f"OpenClaw model status returned invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise OpenClawProviderError("OpenClaw model status JSON was not an object")
    resolved_model = _optional_text(payload.get("resolvedDefault")) or _optional_text(payload.get("defaultModel"))
    default_model = _optional_text(payload.get("defaultModel"))
    selected_provider = resolved_model.split("/", 1)[0] if resolved_model and "/" in resolved_model else None
    return OpenClawModelSelection(
        default_model=default_model,
        resolved_model=resolved_model,
        selected_provider=selected_provider,
        config_path=_optional_text(payload.get("configPath")),
        reason="resolved from active OpenClaw model status",
    )


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _provider_from_model(model: str | None) -> str | None:
    if not model or "/" not in model:
        return None
    provider, _, _ = model.partition("/")
    return provider or None
