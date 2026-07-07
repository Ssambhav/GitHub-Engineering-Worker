"""Registered EngineeringTool wrapper for generic browser automation."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

from browser.contracts import BROWSER_CAPABILITIES, BROWSER_TOOL_ID
from browser.configuration import BrowserConfiguration
from browser.runtime import BrowserRuntime
from tools.base import EngineeringTool
from tools.context import ToolContext, ToolRequest
from tools.metadata import ToolCapabilities, ToolMetadata
from tools.results import ToolArtifact, ToolResult


class BrowserAutomationTool(EngineeringTool):
    """Generic Playwright browser automation tool."""

    metadata = ToolMetadata(
        identifier=BROWSER_TOOL_ID,
        name="Browser Automation Tool",
        version="1.0.0",
        description="Generic Playwright browser automation for navigation, interaction, reading, vision, and sessions.",
        capabilities=ToolCapabilities(BROWSER_CAPABILITIES),
        owner="browser",
        side_effects=("read", "write", "network", "execute"),
        idempotency="conditionally_idempotent",
        input_schema={
            "type": "object",
            "required": ("action",),
            "properties": {
                "action": {"type": "string"},
                "browser_type": {"enum": ("chromium", "firefox", "webkit")},
                "headless": {"type": "boolean"},
                "url": {"type": "string"},
                "selector": {"type": "string"},
            },
        },
    )

    def __init__(self, runtime: BrowserRuntime | None = None) -> None:
        self.runtime = runtime

    @classmethod
    def required_inputs(cls) -> tuple[str, ...]:
        return ("action",)

    def initialize(self, context: ToolContext) -> None:
        super().initialize(context)
        if self.runtime is None:
            artifacts_root = context.configuration.workspace_root / "runtime" / "tmp" / "browser"
            self.runtime = BrowserRuntime(
                BrowserConfiguration(
                    artifacts_path=artifacts_root,
                    downloads_path=artifacts_root / "downloads",
                )
            )

    def execute(self, request: ToolRequest, context: ToolContext, prepared: Mapping[str, Any]) -> ToolResult:
        if self.runtime is None:
            raise RuntimeError("browser runtime was not initialized")
        result = self.runtime.perform(str(request.inputs["action"]), request.inputs)
        artifacts = tuple(
            ToolArtifact(
                artifact_id=artifact.artifact_id,
                kind=artifact.kind,
                path=artifact.path,
                metadata=artifact.metadata,
            )
            for artifact in (*result.artifacts, *result.screenshots)
        )
        output = {
            "success": result.success,
            "action": result.action,
            "execution_time_ms": result.execution_time_ms,
            "url": result.url,
            "page_title": result.page_title,
            "data": self._json_safe(result.data),
            "artifacts": tuple(asdict(artifact) for artifact in result.artifacts),
            "screenshots": tuple(asdict(screenshot) for screenshot in result.screenshots),
            "errors": result.errors,
            "warnings": result.warnings,
        }
        if result.success:
            return ToolResult.ok(
                metadata=self.metadata,
                structured_output=output,
                artifacts=artifacts,
                warnings=result.warnings,
            )
        return ToolResult.failure(
            metadata=self.metadata,
            error="; ".join(result.errors) or "browser action failed",
            execution_time_ms=result.execution_time_ms,
            structured_output=output,
        )

    def cleanup(self, context: ToolContext) -> None:
        context.logger.debug("browser tool action complete", tool_id=self.metadata.identifier)

    def shutdown(self) -> ToolResult:
        if self.runtime is None:
            return ToolResult.ok(metadata=self.metadata, structured_output={"closed": True})
        result = self.runtime.shutdown()
        return ToolResult.ok(metadata=self.metadata, structured_output={"closed": result.success})

    def _json_safe(self, value: Any) -> Any:
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, Mapping):
            return {str(key): self._json_safe(item) for key, item in value.items()}
        if isinstance(value, tuple):
            return tuple(self._json_safe(item) for item in value)
        if isinstance(value, list):
            return [self._json_safe(item) for item in value]
        return value
