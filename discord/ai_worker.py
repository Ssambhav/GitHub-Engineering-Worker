"""OpenClaw-backed Discord front end for the engineering worker."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping
from urllib.error import URLError
from urllib.request import urlopen

from audit import AuditEntry, AuditLogger
from decision.engine import JsonlDecisionMemory
from engineering.providers.openclaw import OpenClawProvider, OpenClawProviderError
from runtime.execution import ExecutionRuntime
from runtime.models.common import IssueRef, RepositoryRef
from tools.context import ToolRequest
from worker.configuration import WorkerConfigurationLoader
from worker.models import WorkerIssue
from worker.runtime_interface import WorkerRuntimeInterface
from playwright.sync_api import sync_playwright


SYSTEM_PROMPT = """You are the brain of the GitHub Engineering Worker, an autonomous AI software engineer.
Return only JSON. Do not execute tools yourself.
Schema:
{
  "reasoning": "brief reason for the plan",
  "actions": [
    {"tool": "general_ai|worker|browser|memory|scheduler", "operation": "name", "inputs": {}}
  ],
  "final_response_intent": "what to tell the human after observations"
}
Use worker for GitHub issue work, issue creation, live issue listing, queue, status, retry, reports, health, pause, and resume.
For requests like "fix issue 4", "work issue #4", "solve issue 4", or "commit issue 4", use worker operation work_issue with issue_number and repository when known.
For natural bug reports in issue-forge, use worker operation create_issue with title, description, labels, and repository when known.
For "what issues are there", "list repo issues", or "issues on my GitHub repo", use worker operation issues. Do not answer from queue/status alone.
Use browser for websites, searches, page reading, screenshots, and interactions.
For requests like "open/read", "search/read", "tell me what is on this page", or "top videos/titles", use browser operation open_and_read with url/query/browser_type inputs when available.
Use memory for remember, forget, or show memory requests.
Use scheduler for natural-language recurring worker schedules.
Use general_ai when no tool is needed.
Prefer combining actions when the user asks for a workflow.
"""


@dataclass(slots=True)
class DiscordAIWorker:
    """Turns Discord messages into OpenClaw plans executed by existing systems."""

    openclaw: OpenClawProvider = field(default_factory=OpenClawProvider)
    runtime: ExecutionRuntime = field(default_factory=ExecutionRuntime)
    worker: WorkerRuntimeInterface = field(default_factory=WorkerRuntimeInterface)
    loader: WorkerConfigurationLoader = field(default_factory=WorkerConfigurationLoader)
    audit_logger: AuditLogger | None = None
    memory: JsonlDecisionMemory | None = None
    last_requests: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.openclaw.model is None and os.environ.get("DISCORD_AI_MODEL"):
            self.openclaw = replace(self.openclaw, model=os.environ["DISCORD_AI_MODEL"])
        _, config = self.loader.load()
        self.audit_logger = self.audit_logger or AuditLogger(config.decisions.audit_directory)
        self.memory = self.memory or JsonlDecisionMemory(config.decisions.audit_directory / "discord-ai-memory.jsonl")
        self.runtime.start()

    def respond(self, message: str, *, user_id: str | None = None, channel_id: str | None = None) -> str:
        message = self._resolve_followup_message(message, channel_id=channel_id)
        try:
            plan = self._plan(message)
        except RuntimeError as exc:
            return f"OpenClaw is currently unavailable, so I cannot execute that Discord request yet. {exc}"
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
        prompt = "\n".join((SYSTEM_PROMPT, "Discord message:", message))
        try:
            text = self.openclaw.infer_text(prompt)
            plan = _json_object(text)
        except OpenClawProviderError as exc:
            raise RuntimeError(f"OpenClaw planning failed: {exc}") from exc
        if not isinstance(plan.get("actions"), list):
            plan["actions"] = [{"tool": "general_ai", "operation": "answer", "inputs": {}}]
        return plan

    def _execute_plan(self, plan: Mapping[str, Any], *, message: str, user_id: str | None, channel_id: str | None) -> list[dict[str, Any]]:
        observations: list[dict[str, Any]] = []
        for index, raw_action in enumerate(plan.get("actions", []), start=1):
            action = raw_action if isinstance(raw_action, Mapping) else {}
            tool = str(action.get("tool") or "general_ai")
            operation = str(action.get("operation") or "answer")
            inputs = action.get("inputs") if isinstance(action.get("inputs"), Mapping) else {}
            try:
                output = self._execute_action(tool, operation, inputs, original_message=message)
                success = True
            except Exception as exc:
                output = {"error": str(exc)}
                success = False
            observation = {"step": index, "tool": tool, "operation": operation, "success": success, "output": output}
            observations.append(observation)
            self._audit_decision(message, observation, user_id=user_id, channel_id=channel_id)
            if self.memory is not None:
                self.memory.propose_update(f"discord:observation:{index}", observation)
        return observations

    def _execute_action(self, tool: str, operation: str, inputs: Mapping[str, Any], *, original_message: str) -> Any:
        if tool == "general_ai":
            return {"answer_required": True}
        if tool == "worker":
            return self._worker(operation, inputs, original_message=original_message)
        if tool == "browser":
            return self._browser(operation, inputs, original_message=original_message)
        if tool == "memory":
            return self._memory(operation, inputs, original_message=original_message)
        if tool == "scheduler":
            return self._scheduler(operation, inputs)
        raise ValueError(f"unsupported planned tool: {tool}")

    def _worker(self, operation: str, inputs: Mapping[str, Any], *, original_message: str) -> str:
        if operation in {"check_now", "check-github", "run", "run_now"}:
            return self.worker.check_now()
        if operation in {"status", "queue", "show_queue"}:
            return self.worker.status()
        if operation in {"issues", "list_issues", "open_issues", "github_issues", "repo_issues"}:
            return self.worker.issues()
        if operation in {"report", "latest_report"}:
            return self.worker.report()
        if operation in {"retry", "retry_failed", "retry_latest_failed"}:
            return self.worker.retry_latest_failed()
        if operation == "health":
            return self.worker.health()
        if operation == "pause":
            return self.worker.pause()
        if operation == "resume":
            return self.worker.resume()
        if operation in {
            "work_issue",
            "fix_issue",
            "solve_issue",
            "issue",
            "commit_issue",
            "handle_issue",
            "process_issue",
            "run_issue",
        }:
            return self.worker.solve_issue(self._issue_number(inputs, original_message), repository=inputs.get("repository"))
        if operation in {"create_issue", "forge_issue", "new_issue"}:
            return self.worker.create_issue(
                title=str(inputs.get("title") or ""),
                description=str(inputs.get("description") or inputs.get("body") or original_message),
                labels=tuple(str(label) for label in inputs.get("labels", ()) if str(label).strip()),
                repository=inputs.get("repository"),
            )
        raise ValueError(f"unsupported worker operation: {operation}")

    def _browser(self, operation: str, inputs: Mapping[str, Any], *, original_message: str) -> Mapping[str, Any]:
        request_inputs = dict(inputs)
        message_lower = original_message.lower()
        if "opera" in message_lower and "browser_type" not in request_inputs:
            request_inputs["browser_type"] = "opera"
        if "browser" in request_inputs and "browser_type" not in request_inputs:
            request_inputs["browser_type"] = request_inputs.pop("browser")
        if self._should_show_browser_window(original_message):
            request_inputs.setdefault("headless", False)
        if str(request_inputs.get("browser_type", "")).lower() == "opera":
            request_inputs.setdefault("headless", False)
        action = request_inputs.pop("action", None) or self._browser_action(operation, request_inputs)
        request_inputs["action"] = action
        self._complete_browser_url(request_inputs, operation=operation, original_message=original_message)
        if self._is_combined_browser_operation(operation, request_inputs, original_message):
            return self._browser_open_and_read(request_inputs, original_message=original_message)
        if self._should_use_main_opera_profile(request_inputs):
            return self._open_main_opera(str(request_inputs["url"]))
        return self._run_browser_tool(request_inputs)

    def _is_combined_browser_operation(self, operation: str, inputs: Mapping[str, Any], original_message: str) -> bool:
        operation_name = operation.lower().replace("-", "_")
        if operation_name in {"open_and_read", "open_read", "read_homepage", "browse_and_read", "search_and_read"}:
            return True
        message = original_message.lower()
        return bool(inputs.get("url")) and any(term in message for term in ("read", "tell me", "top 3", "top three", "what's on", "whats on"))

    def _browser_open_and_read(self, inputs: Mapping[str, Any], *, original_message: str) -> Mapping[str, Any]:
        if self._should_use_main_opera_profile(inputs):
            return self._main_opera_open_and_read(inputs, original_message=original_message)
        open_inputs = dict(inputs)
        open_inputs["action"] = "open_url"
        open_inputs.setdefault("wait_until", "domcontentloaded")
        open_result = self._run_browser_tool(open_inputs)
        if not open_result["success"]:
            return {"success": False, "status": "failed", "steps": [open_result], "errors": open_result.get("errors", ())}

        wait_result = self._run_browser_tool({"action": "wait_for_network_idle"})
        links_result = self._run_browser_tool({"action": "read_links"})
        text_result = self._run_browser_tool({"action": "read_visible_text"})
        steps = [open_result, wait_result, links_result, text_result]
        output: dict[str, Any] = {
            "url": (open_result.get("output") or {}).get("url"),
            "page_title": (open_result.get("output") or {}).get("page_title"),
        }
        if "youtube" in original_message.lower() or "youtube.com" in str(output.get("url", "")):
            titles = self._youtube_video_titles(links_result, text_result)
            output["top_video_titles"] = titles[: self._requested_count(original_message, default=3)]
            if not output["top_video_titles"]:
                output["note"] = "No visible YouTube video titles were found on the loaded homepage. YouTube may be showing a signed-out or empty personalized feed in the worker browser profile."
        output["visible_text_excerpt"] = self._visible_text_excerpt(text_result)
        return {"success": True, "status": "success", "operation": "open_and_read", "steps": steps, "output": output, "errors": ()}

    def _run_browser_tool(self, inputs: Mapping[str, Any]) -> Mapping[str, Any]:
        context = self._tool_context()
        request = ToolRequest(tool_id="browser.automation", capability="browser.navigate", inputs=inputs)
        assert self.runtime.tool_executor is not None
        result = self.runtime.tool_executor.execute(request, self.runtime.tool_executor.create_context(context, request))
        return {"success": result.success, "status": result.status.value, "output": dict(result.structured_output), "errors": result.errors}

    def _should_use_main_opera_profile(self, inputs: Mapping[str, Any]) -> bool:
        return (
            str(inputs.get("browser_type", "")).lower() == "opera"
            and str(inputs.get("action", "")).lower() == "open_url"
            and bool(inputs.get("url"))
            and _env_bool("GEW_USE_MAIN_BROWSER_PROFILE")
        )

    def _should_show_browser_window(self, message: str) -> bool:
        return _env_bool("GEW_BROWSER_VISIBLE") or any(term in message.lower() for term in ("open", "show", "watch", "youtube", "github"))

    def _open_main_opera(self, url: str) -> Mapping[str, Any]:
        executable = os.environ.get("OPERA_EXECUTABLE") or r"C:\Users\HP\AppData\Local\Programs\Opera\opera.exe"
        if not Path(executable).exists():
            raise RuntimeError(f"Opera executable not found: {executable}")
        subprocess.Popen([executable, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"success": True, "status": "success", "output": {"url": url, "browser_type": "opera", "profile": "main"}}

    def _main_opera_open_and_read(self, inputs: Mapping[str, Any], *, original_message: str) -> Mapping[str, Any]:
        url = str(inputs.get("url") or "about:blank")
        port = int(os.environ.get("OPERA_REMOTE_DEBUGGING_PORT", "9223"))
        self._ensure_main_opera_debuggable(url, port)
        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            page = context.pages[-1] if context.pages else context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            try:
                page.wait_for_load_state("networkidle", timeout=15_000)
            except Exception:
                pass
            page.bring_to_front()
            links = page.eval_on_selector_all(
                "a",
                "(els) => els.map((a) => ({text: a.innerText, href: a.href, title: a.title}))",
            )
            visible_text = page.locator("body").inner_text(timeout=15_000)
            output: dict[str, Any] = {"url": page.url, "page_title": page.title(), "profile": "main-opera-cdp"}
            text_result = {"output": {"data": {"value": visible_text}}}
            links_result = {"output": {"data": {"links": links}}}
            if "youtube" in original_message.lower() or "youtube.com" in page.url:
                titles = self._youtube_dom_video_titles(page) or self._youtube_video_titles(links_result, text_result)
                output["top_video_titles"] = titles[: self._requested_count(original_message, default=3)]
                if not output["top_video_titles"]:
                    output["note"] = "No visible YouTube video titles were found in the main Opera page."
            output["visible_text_excerpt"] = visible_text.strip()[:1800]
            return {"success": True, "status": "success", "operation": "main_opera_open_and_read", "output": output, "errors": ()}

    def _ensure_main_opera_debuggable(self, url: str, port: int) -> None:
        if self._cdp_available(port):
            return
        executable = Path(os.environ.get("OPERA_EXECUTABLE") or r"C:\Users\HP\AppData\Local\Programs\Opera\opera.exe")
        if not executable.exists():
            raise RuntimeError(f"Opera executable not found: {executable}")
        profile_path = Path(os.environ.get("OPERA_USER_DATA_DIR") or (Path(os.environ["APPDATA"]) / "Opera Software" / "Opera Stable"))
        args = [
            str(executable),
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile_path}",
            "--no-first-run",
            url,
        ]
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(20):
            if self._cdp_available(port):
                return
            time.sleep(0.5)
        if _env_bool("GEW_RESTART_OPERA_FOR_CONTROL"):
            subprocess.run(["taskkill", "/IM", "opera.exe", "/F"], capture_output=True, text=True)
            time.sleep(2)
            subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(20):
                if self._cdp_available(port):
                    return
                time.sleep(0.5)
        raise RuntimeError(
            "Main Opera is not controllable yet. Close all Opera windows once, then ask again, or keep GEW_RESTART_OPERA_FOR_CONTROL=true so the worker can restart Opera with remote debugging."
        )

    def _cdp_available(self, port: int) -> bool:
        try:
            with urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1) as response:
                if response.status != 200:
                    return False
                body = response.read().decode("utf-8", errors="replace").lower()
                return "opera" in body or "opr" in body
        except (OSError, URLError):
            return False

    def _complete_browser_url(self, inputs: dict[str, Any], *, operation: str, original_message: str) -> None:
        if str(inputs.get("action")) != "open_url":
            return
        query = str(inputs.get("query") or "").strip()
        message_lower = original_message.lower()
        if "youtube" in message_lower:
            if any(term in message_lower for term in ("homepage", "home page", "front page")) and not query:
                inputs["url"] = "https://www.youtube.com/"
                return
            if not query:
                query = self._extract_search_query(original_message)
            if not query:
                inputs["url"] = "https://www.youtube.com/"
                return
            inputs["url"] = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
            return
        if inputs.get("url"):
            return
        if query:
            inputs["url"] = f"https://www.google.com/search?q={query.replace(' ', '+')}"

    def _extract_search_query(self, message: str) -> str:
        match = re.search(r"search(?: for)?\\s+(.+)$", message, re.IGNORECASE)
        if not match:
            return ""
        query = match.group(1).strip()
        query = re.sub(r"\\s+(?:in|on)\\s+(?:opera|chrome|edge|firefox)\\b.*$", "", query, flags=re.IGNORECASE)
        return query.strip(" .")

    def _memory(self, operation: str, inputs: Mapping[str, Any], *, original_message: str) -> Mapping[str, Any]:
        assert self.memory is not None
        key = str(inputs.get("key") or "discord:user")
        if operation in {"remember", "store"}:
            value = {"text": str(inputs.get("value") or original_message)}
            self.memory.propose_update(key, value)
            return {"remembered": key, "value": value}
        if operation in {"show", "read"}:
            return {"key": key, "value": self.memory.read(key)}
        if operation == "forget":
            self.memory.propose_update(key, {"forgotten": True})
            return {"forgotten": key}
        raise ValueError(f"unsupported memory operation: {operation}")

    def _scheduler(self, operation: str, inputs: Mapping[str, Any]) -> str:
        if operation == "pause":
            return self.worker.pause()
        if operation == "resume":
            return self.worker.resume()
        if operation in {"schedule", "recurring_check", "create_recurring_schedule", "set_recurring_schedule"}:
            return self.worker.schedule(str(inputs.get("schedule") or inputs.get("text") or inputs.get("request") or ""))
        raise ValueError(f"unsupported scheduler operation: {operation}")

    def _final_response(self, message: str, plan: Mapping[str, Any], observations: list[dict[str, Any]]) -> str:
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
            return "I could not produce a response because OpenClaw did not return a plan."
        lines = ["I ran the requested workflow:"]
        for item in observations:
            status = "ok" if item["success"] else "failed"
            lines.append(f"- {item['tool']}.{item['operation']}: {status}")
        return "\n".join(lines)

    def _browser_response(self, observations: list[dict[str, Any]]) -> str:
        for item in observations:
            if item.get("tool") != "browser" or not item.get("success"):
                continue
            output = item.get("output")
            if not isinstance(output, Mapping):
                continue
            data = output.get("output")
            if not isinstance(data, Mapping):
                continue
            titles = data.get("top_video_titles")
            if isinstance(titles, list) and titles:
                lines = ["Top visible YouTube video titles:"]
                lines.extend(f"{index}. {title}" for index, title in enumerate(titles[:3], start=1))
                return "\n".join(lines)
            note = data.get("note")
            if note:
                return str(note)
            excerpt = str(data.get("visible_text_excerpt") or "").strip()
            if excerpt:
                return excerpt[:1200]
        return ""

    def _tool_context(self):
        _, config = self.loader.load()
        repository = config.repositories[0] if config.repositories else None
        repo_ref = RepositoryRef(
            provider="github",
            owner=repository.owner if repository else "local",
            name=repository.name if repository else "workspace",
            default_branch=repository.default_branch if repository else config.default_branch,
        )
        issue_ref = IssueRef(provider="discord", repository=repo_ref.full_name, issue_number=0, title="Discord request")
        return self.runtime.create_context(issue=issue_ref, repository=repo_ref)

    def _browser_action(self, operation: str, inputs: Mapping[str, Any]) -> str:
        operation_name = operation.lower().replace("-", "_")
        if operation_name in {"open", "open_url", "navigate", "search", "open_and_read", "open_read", "read_homepage", "browse_and_read", "search_and_read"}:
            if operation == "search" and "url" not in inputs:
                query = str(inputs.get("query") or "")
                if isinstance(inputs, dict):
                    inputs["url"] = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            return "open_url"
        if operation_name in {"read", "summarize", "read_visible_text"}:
            return "read_visible_text"
        if operation_name in {"screenshot", "take_screenshot"}:
            return "take_screenshot"
        return operation

    def _youtube_video_titles(self, links_result: Mapping[str, Any], text_result: Mapping[str, Any]) -> list[str]:
        links = (((links_result.get("output") or {}).get("data") or {}).get("links") or ())
        titles: list[str] = []
        seen: set[str] = set()
        for link in links:
            if not isinstance(link, Mapping):
                continue
            href = str(link.get("href") or "")
            text = self._clean_video_title(str(link.get("text") or link.get("title") or ""))
            if "watch" not in href or not text or text in seen:
                continue
            seen.add(text)
            titles.append(text)
        if titles:
            return titles
        visible = self._visible_text_excerpt(text_result, limit=4000)
        fallback: list[str] = []
        for line in visible.splitlines():
            title = self._clean_video_title(line)
            if title and title not in seen:
                seen.add(title)
                fallback.append(title)
        return fallback

    def _youtube_dom_video_titles(self, page: Any) -> list[str]:
        selectors = [
            "ytd-rich-item-renderer #video-title",
            "ytd-video-renderer #video-title",
            "a#video-title",
            "a#video-title-link",
        ]
        titles: list[str] = []
        seen: set[str] = set()
        for selector in selectors:
            try:
                values = page.eval_on_selector_all(
                    selector,
                    "(els) => els.map((el) => (el.getAttribute('title') || el.innerText || el.textContent || '').trim())",
                )
            except Exception:
                continue
            for value in values:
                title = self._clean_video_title(str(value))
                if title and title not in seen:
                    seen.add(title)
                    titles.append(title)
            if titles:
                return titles
        return titles

    def _clean_video_title(self, value: str) -> str:
        text = " ".join(value.split())
        if not text or len(text) < 4:
            return ""
        lowered = text.lower()
        blocked = {
            "youtube",
            "home",
            "shorts",
            "subscriptions",
            "library",
            "history",
            "sign in",
            "search",
            "notifications",
            "skip navigation",
            "try searching to get started",
            "start watching videos to help us build a feed of videos that you'll love.",
        }
        if lowered in blocked or lowered.endswith(" views") or lowered in {"new", "live", "watch"}:
            return ""
        if re.fullmatch(r"\d{1,2}:\d{2}(?::\d{2})?", lowered):
            return ""
        return text[:180]

    def _visible_text_excerpt(self, text_result: Mapping[str, Any], *, limit: int = 1800) -> str:
        value = (((text_result.get("output") or {}).get("data") or {}).get("value") or "")
        return str(value).strip()[:limit]

    def _requested_count(self, message: str, *, default: int) -> int:
        match = re.search(r"top\s+(\\d+)", message, re.IGNORECASE)
        if not match:
            return default
        return max(1, min(10, int(match.group(1))))

    def _issue_number(self, inputs: Mapping[str, Any], message: str) -> int:
        if inputs.get("issue_number"):
            return int(inputs["issue_number"])
        match = re.search(r"#(\d+)|issue\s+(\d+)", message, re.IGNORECASE)
        if not match:
            raise ValueError("issue number is required")
        return int(next(value for value in match.groups() if value))

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


def _env_bool(name: str) -> bool:
    return os.environ.get(name, "").lower() in {"1", "true", "yes", "on"}
