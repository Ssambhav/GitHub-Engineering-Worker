"""Verification loop support built on the registered browser automation tool."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from engineering.models import EngineeringIssue, IssueUnderstanding, VerificationAction, VerificationResult
from runtime.models.common import IssueRef, RepositoryRef
from tools.context import ToolRequest
from tools.results import ToolResult
from worker.models import WorkerRepository


@dataclass(slots=True)
class BrowserVerifier:
    """Runs browser-based issue verification against acceptance criteria."""

    runtime: Any

    _STOP_WORDS = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "when",
        "then",
        "into",
        "does",
        "should",
        "after",
        "before",
        "user",
        "page",
        "screen",
        "issue",
        "expected",
        "actual",
        "behavior",
    }

    def verify(
        self,
        *,
        issue: EngineeringIssue,
        understanding: IssueUnderstanding,
        repository: WorkerRepository,
        repository_path: Path,
    ) -> VerificationResult:
        target_url = self._extract_target_url(issue)
        if not target_url:
            return VerificationResult(
                attempted=False,
                passed=False,
                summary="Verification could not start because no application URL was found in the issue body.",
                errors=("missing application URL for browser verification",),
            )

        if self.runtime.configuration is None:
            self.runtime.start()
        execution = self.runtime.create_context(
            issue=IssueRef(provider="github", repository=issue.repository, issue_number=issue.number, title=issue.title, url=issue.url),
            repository=RepositoryRef(provider="github", owner=repository.owner, name=repository.name, default_branch=repository.default_branch),
        ).with_data("repository_path", str(repository_path)).with_data("browser_url", target_url)
        tool_context = self.runtime.tool_executor.create_context(execution)

        actions: list[VerificationAction] = []
        screenshots: list[str] = []

        def run_browser(action: str, **inputs: Any) -> ToolResult:
            result = self.runtime.tool_executor.execute(
                ToolRequest(
                    tool_id="browser.automation",
                    inputs={
                        "action": action,
                        "profile_name": "default",
                        "profiles_root": "runtime/browser_profiles",
                        **inputs,
                    },
                ),
                tool_context,
            )
            screenshot_paths = tuple(artifact.path for artifact in result.artifacts if artifact.kind == "screenshot" and artifact.path)
            screenshots.extend(path for path in screenshot_paths if path not in screenshots)
            output = result.structured_output
            data = output.get("data", {}) if isinstance(output, dict) else {}
            actions.append(
                VerificationAction(
                    action=action,
                    success=result.success,
                    url=str(output.get("url", "")) if isinstance(output, dict) else "",
                    page_title=str(output.get("page_title", "")) if isinstance(output, dict) else "",
                    details=self._details_for(action, data),
                    screenshot_paths=screenshot_paths,
                    errors=result.errors,
                )
            )
            return result

        launch = run_browser("launch", headless=True)
        open_result = run_browser("open_url", url=target_url) if launch.success else launch
        if open_result.success:
            run_browser("wait_for_network_idle")
        title_result = run_browser("read_page_title") if open_result.success else open_result
        text_result = run_browser("read_visible_text") if open_result.success else open_result
        if open_result.success:
            run_browser("full_page_screenshot", path=f"verification-{issue.number}.png")

        visible_text = self._extract_value(text_result)
        title = self._extract_value(title_result)
        evaluation = self._evaluate(understanding=understanding, title=title, visible_text=visible_text)
        errors = tuple(error for action in actions for error in action.errors)
        passed = not errors and evaluation["passed"]
        summary = str(evaluation["summary"])
        if errors:
            summary = f"Browser verification failed during tool execution: {'; '.join(errors)}"

        return VerificationResult(
            attempted=True,
            passed=passed,
            summary=summary,
            target_url=target_url,
            issue_reproduced=bool(evaluation["issue_reproduced"]),
            expected_behavior_verified=bool(evaluation["expected_behavior_verified"]),
            visible_text_excerpt=visible_text[:4000],
            screenshot_paths=tuple(screenshots),
            actions=tuple(actions),
            warnings=tuple(str(item) for item in evaluation["warnings"]),
            errors=errors or tuple(str(item) for item in evaluation["errors"]),
        )

    def _extract_target_url(self, issue: EngineeringIssue) -> str | None:
        text = " ".join(part for part in (issue.body or "", issue.url or "") if part)
        matches = re.findall(r"(https?://[^\s)]+|http://localhost:\d+[^\s)]*|https://localhost:\d+[^\s)]*)", text, flags=re.IGNORECASE)
        for match in matches:
            if "github.com/" not in match:
                return match.rstrip(".,)")
        return None

    def _extract_value(self, result: ToolResult) -> str:
        output = result.structured_output
        if not isinstance(output, dict):
            return ""
        data = output.get("data", {})
        if isinstance(data, dict):
            value = data.get("value", "")
            return str(value)
        return ""

    def _evaluate(self, *, understanding: IssueUnderstanding, title: str, visible_text: str) -> dict[str, Any]:
        haystack = f"{title}\n{visible_text}".lower()
        expected_keywords = self._keywords((understanding.expected_behavior, *understanding.acceptance_criteria))
        actual_keywords = self._keywords((understanding.actual_behavior, understanding.problem))
        expected_hits = [word for word in expected_keywords if word in haystack]
        actual_hits = [word for word in actual_keywords if word in haystack]
        issue_reproduced = bool(actual_hits)
        expected_behavior_verified = bool(expected_hits) and len(expected_hits) >= max(1, min(2, len(expected_keywords)))
        passed = expected_behavior_verified and not issue_reproduced
        warnings: list[str] = []
        if not expected_keywords:
            warnings.append("acceptance criteria did not produce strong verification keywords")
        errors: list[str] = []
        if not passed:
            if not expected_hits:
                errors.append("expected acceptance criteria were not observed in browser evidence")
            if actual_hits:
                errors.append(f"issue symptoms still appear in browser evidence: {', '.join(actual_hits[:6])}")
        summary = (
            "Acceptance criteria matched browser evidence and the reported symptoms were not observed."
            if passed
            else "Browser evidence did not satisfy the issue acceptance criteria."
        )
        return {
            "passed": passed,
            "summary": summary,
            "issue_reproduced": issue_reproduced,
            "expected_behavior_verified": expected_behavior_verified,
            "warnings": tuple(warnings),
            "errors": tuple(errors),
        }

    def _keywords(self, texts: Iterable[str]) -> tuple[str, ...]:
        words: list[str] = []
        for text in texts:
            words.extend(re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{3,}", text.lower()))
        filtered = [word for word in words if word not in self._STOP_WORDS]
        return tuple(dict.fromkeys(filtered[:24]))

    def _details_for(self, action: str, data: Any) -> str:
        if not isinstance(data, dict):
            return ""
        if action in {"read_page_title", "read_visible_text"}:
            return str(data.get("value", ""))[:200]
        return ", ".join(f"{key}={value}" for key, value in list(data.items())[:4])
