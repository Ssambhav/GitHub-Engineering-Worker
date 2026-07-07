"""OpenClaw-backed Discord front end for the engineering worker."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, replace
from typing import Any, Mapping

from audit import AuditEntry, AuditLogger
from decision.engine import JsonlDecisionMemory
from engineering.providers.openclaw import OpenClawProvider, OpenClawProviderError
from worker.configuration import WorkerConfigurationLoader
from worker.runtime_interface import WorkerRuntimeInterface


SYSTEM_PROMPT = """You are the brain of the GitHub Engineering Worker, an autonomous AI software engineer.
Return only JSON. Do not execute tools yourself.
Schema:
{
  "reasoning": "brief reason for the plan",
  "actions": [
    {"tool": "general_ai|runtime", "operation": "registered capability name", "inputs": {}}
  ],
  "final_response_intent": "what to tell the human after observations"
}
All non-chat actions must go through the runtime capability registry supplied by the application.
Never invent unsupported operations.
If the exact capability is unclear, still choose tool "runtime" and use the closest registered capability or leave operation empty.
Use general_ai when no tool is needed.
Prefer combining actions when the user asks for a workflow.
"""


@dataclass(slots=True)
class DiscordAIWorker:
    """Turns Discord messages into OpenClaw plans executed by existing systems."""

    openclaw: OpenClawProvider = field(default_factory=OpenClawProvider)
    worker: WorkerRuntimeInterface = field(default_factory=WorkerRuntimeInterface)
    loader: WorkerConfigurationLoader = field(default_factory=WorkerConfigurationLoader)
    audit_logger: AuditLogger | None = None
    memory: JsonlDecisionMemory | None = None
    last_requests: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _, config = self.loader.load()
        if config.model and self.openclaw.model != config.model:
            self.openclaw = replace(self.openclaw, model=config.model)
        self.audit_logger = self.audit_logger or AuditLogger(config.decisions.audit_directory)
        self.memory = self.memory or JsonlDecisionMemory(config.decisions.audit_directory / "discord-ai-memory.jsonl")

    def respond(self, message: str, *, user_id: str | None = None, channel_id: str | None = None) -> str:
        message = self._resolve_followup_message(message, channel_id=channel_id)
        try:
            plan = self._plan(message)
        except RuntimeError as exc:
            return self._planning_error_response(exc)
        observations = self._execute_plan(plan, message=message, user_id=user_id, channel_id=channel_id)
        if not self._is_followup_command(message) and channel_id:
            self.last_requests[channel_id] = message
        return self._final_response(message, plan, observations)

    def _resolve_followup_message(self, message: str, *, channel_id: str | None) -> str:
        if not channel_id or not self._is_followup_command(message):
            return message
        previous = self.last_requests.get(channel_id)
        if not previous:
            return message
        return previous

    def _is_followup_command(self, message: str) -> bool:
        normalized = " ".join(message.lower().strip().split())
        return normalized in {"now do it", "do it", "try again", "run it", "again", "now"} or normalized.startswith("now do it ")

    def _plan(self, message: str) -> dict[str, Any]:
        direct = self._direct_runtime_plan(message)
        if direct is not None:
            return direct
        prompt = "\n".join((SYSTEM_PROMPT, "Registered worker capabilities:", self._worker_capability_prompt(), "Discord message:", message))
        try:
            text = self.openclaw.infer_text(prompt)
            plan = _json_object(text)
        except OpenClawProviderError as exc:
            raise RuntimeError(f"OpenClaw planning failed: {exc}") from exc
        if not isinstance(plan.get("actions"), list):
            plan["actions"] = [{"tool": "general_ai", "operation": "answer", "inputs": {}}]
        return plan

    def _direct_runtime_plan(self, message: str) -> dict[str, Any] | None:
        resolution = self.worker.resolve_capability("", message=message, inputs={})
        if not resolution.supported or resolution.capability is None:
            return None
        return {
            "reasoning": "Direct runtime command resolved from Discord message.",
            "actions": [{"tool": "runtime", "operation": resolution.capability.name, "inputs": {}}],
            "final_response_intent": "Report the runtime action result directly.",
        }

    def _worker_capability_prompt(self) -> str:
        return json.dumps(
            {
                name: {
                    "description": capability.description,
                    "requires_issue_number": capability.requires_issue_number,
                    "requires_description": capability.requires_description,
                }
                for name, capability in self.worker.capabilities().items()
            },
            sort_keys=True,
        )

    def _execute_plan(self, plan: Mapping[str, Any], *, message: str, user_id: str | None, channel_id: str | None) -> list[dict[str, Any]]:
        observations: list[dict[str, Any]] = []
        for index, raw_action in enumerate(plan.get("actions", []), start=1):
            action = raw_action if isinstance(raw_action, Mapping) else {}
            requested_tool = str(action.get("tool") or "general_ai")
            tool = self._normalize_planned_tool(requested_tool)
            operation = str(action.get("operation") or "answer")
            inputs = action.get("inputs") if isinstance(action.get("inputs"), Mapping) else {}
            validation = self._validate_action(tool, operation, inputs, original_message=message)
            if not validation["valid"]:
                observation = {
                    "step": index,
                    "tool": tool,
                    "operation": operation,
                    "success": False,
                    "output": {**validation, "requested_tool": requested_tool},
                }
                observations.append(observation)
                self._audit_decision(message, observation, user_id=user_id, channel_id=channel_id)
                if self.memory is not None:
                    self.memory.propose_update(f"discord:observation:{index}", observation)
                continue
            operation = str(validation.get("operation") or operation)
            try:
                output = self._execute_action(tool, operation, inputs, original_message=message)
                success = True
            except Exception as exc:
                output = {"error": str(exc)}
                success = False
            observation = {
                "step": index,
                "tool": tool,
                "operation": operation,
                "success": success,
                "output": output,
            }
            observations.append(observation)
            self._audit_decision(message, observation, user_id=user_id, channel_id=channel_id)
            if self.memory is not None:
                self.memory.propose_update(f"discord:observation:{index}", observation)
        return observations

    def _execute_action(self, tool: str, operation: str, inputs: Mapping[str, Any], *, original_message: str) -> Any:
        if tool == "general_ai":
            return {"answer_required": True}
        if tool == "runtime":
            return self._runtime(operation, inputs, original_message=original_message)
        raise ValueError(f"unsupported planned tool: {tool}")

    def _runtime(self, operation: str, inputs: Mapping[str, Any], *, original_message: str) -> str:
        resolution = self.worker.resolve_capability(operation, message=original_message, inputs=inputs)
        if not resolution.supported or resolution.capability is None:
            return json.dumps(self._unsupported_capability(operation, resolution), indent=2, sort_keys=True)
        return self.worker.execute_capability(resolution.capability, inputs=inputs, message=original_message)

    def _validate_action(self, tool: str, operation: str, inputs: Mapping[str, Any], *, original_message: str) -> dict[str, Any]:
        tool = self._normalize_planned_tool(tool)
        if tool != "runtime":
            return {"valid": True, "operation": operation}
        resolution = self.worker.resolve_capability(operation, message=original_message, inputs=inputs)
        if resolution.supported and resolution.capability is not None:
            return {
                "valid": True,
                "operation": resolution.capability.name,
                "requested_operation": operation,
                "reason": resolution.reason,
            }
        return self._unsupported_capability(operation, resolution)

    def _unsupported_capability(self, operation: str, resolution: Any) -> dict[str, Any]:
        return {
            "valid": False,
            "status": "unresolved_runtime_request",
            "requested_operation": operation,
            "closest_capability": resolution.capability.name if resolution.capability is not None else None,
            "equivalent": False,
            "confidence": resolution.confidence,
            "reason": f"Stage: command routing\nReason: {resolution.reason}\nSuggested action: rephrase the request with an issue number or queue action.",
            "available_capabilities": sorted(self.worker.capabilities().keys()),
            "candidates": list(resolution.candidates),
        }

    def _normalize_planned_tool(self, tool: str) -> str:
        normalized = str(tool or "").strip().lower()
        if normalized in {"", "general_ai", "runtime"}:
            return normalized or "general_ai"
        tokens = {part for part in re.split(r"[^a-z0-9_.]+", normalized) if part}
        if "runtime" in tokens:
            return "runtime"
        if "general_ai" in tokens:
            return "general_ai"
        return normalized

    def _final_response(self, message: str, plan: Mapping[str, Any], observations: list[dict[str, Any]]) -> str:
        runtime_owned = self._runtime_owned_response(plan, observations)
        if runtime_owned is not None:
            return runtime_owned
        browser_response = self._browser_response(observations)
        if browser_response:
            return browser_response
        prompt = "\n".join(
            (
                "You are the GitHub Engineering Worker speaking in Discord.",
                "Write a concise teammate-style reply based only on the message, plan, and observations.",
                f"Message: {message}",
                f"Plan: {json.dumps(plan, default=str)}",
                f"Observations: {json.dumps(observations, default=str)}",
            )
        )
        try:
            return self.openclaw.infer_text(prompt).strip()
        except OpenClawProviderError:
            return self._fallback_response(observations)

    def _fallback_response(self, observations: list[dict[str, Any]]) -> str:
        if not observations:
            return "Stage: planning\nReason: OpenClaw did not return a runtime plan.\nSuggested action: try the request again after checking the worker model/provider."
        lines = ["Requested workflow executed:"]
        for item in observations:
            status = "ok" if item["success"] else "failed"
            lines.append(f"- {item['tool']}.{item['operation']}: {status}")
        return "\n".join(lines)

    def _runtime_owned_response(self, plan: Mapping[str, Any], observations: list[dict[str, Any]]) -> str | None:
        if not self._runtime_owns_response(plan, observations):
            return None
        messages: list[str] = []
        for item in observations:
            if item.get("tool") != "runtime":
                continue
            output = item.get("output")
            if isinstance(output, str):
                messages.append(output)
                continue
            if isinstance(output, Mapping) and "error" in output:
                messages.append(
                    "Stage: runtime execution\n"
                    f"Reason: {output['error']}\n"
                    "Suggested action: retry the command after the worker finishes its current filesystem or queue operation."
                )
        if not messages:
            return None
        return "\n\n".join(messages)

    def _runtime_owns_response(self, plan: Mapping[str, Any], observations: list[dict[str, Any]]) -> bool:
        if not observations:
            return False
        runtime_observations = [item for item in observations if item.get("tool") == "runtime"]
        if not runtime_observations:
            return False
        actions = plan.get("actions", [])
        planned_tools = {
            self._normalize_planned_tool(str(action.get("tool") or "general_ai"))
            for action in actions
            if isinstance(action, Mapping)
        }
        return bool(planned_tools) and planned_tools <= {"runtime"}

    def _browser_response(self, observations: list[dict[str, Any]]) -> str:
        for item in observations:
            if item.get("tool") != "runtime" or not item.get("success"):
                continue
            output = item.get("output")
            if not isinstance(output, str):
                continue
            try:
                payload = json.loads(output)
            except json.JSONDecodeError:
                continue
            data = payload.get("output")
            if not isinstance(data, Mapping):
                continue
            excerpt = json.dumps(data, indent=2, sort_keys=True, default=str)
            if excerpt:
                return excerpt[:1200]
        return ""

    def _planning_error_response(self, exc: RuntimeError) -> str:
        detail = str(exc)
        if _looks_like_google_quota_error(detail):
            return (
                "OpenClaw planning is hitting the currently selected Google Gemini quota limit. "
                "This Discord bot uses OpenClaw, and OpenClaw is still pointed at Google right now. "
                "Set `WORKER_MODEL=openai/gpt-5.4` in `.env` and make sure OpenClaw is authenticated with OpenAI/Codex, then restart the bot."
            )
        return f"OpenClaw is currently unavailable, so I cannot execute that Discord request yet. {detail}"

    def _audit_decision(self, message: str, observation: Mapping[str, Any], *, user_id: str | None, channel_id: str | None) -> None:
        if self.audit_logger is None:
            return
        self.audit_logger.append(
            AuditEntry(
                execution_id="discord_ai_worker",
                issue="discord",
                repository="discord",
                current_stage="Discord AI Worker",
                current_agent="openclaw",
                current_tool=str(observation.get("tool")),
                action="discord.ai_worker.step",
                decision=str(message),
                result="success" if observation.get("success") else "failed",
                metadata={"operation": observation.get("operation"), "user_id": user_id, "channel_id": channel_id},
            )
        )


def _json_object(text: str) -> dict[str, Any]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise OpenClawProviderError("OpenClaw did not return a JSON plan")
        data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise OpenClawProviderError("OpenClaw JSON plan was not an object")
    return data


def _looks_like_google_quota_error(detail: str) -> bool:
    normalized = detail.lower()
    return (
        "provider \"google\"" in normalized
        or "gemini" in normalized
        or "quota exceeded" in normalized
        or "resource_exhausted" in normalized
        or "429" in normalized and "google" in normalized
    )
