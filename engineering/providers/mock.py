"""Deterministic provider used when no API key is configured."""

from __future__ import annotations

from dataclasses import dataclass
import re

from engineering.models.core import PatchResponse, ProviderRequest


@dataclass(frozen=True, slots=True)
class MockProvider:
    """Returns a deterministic sample patch for smoke tests and offline runs."""

    name: str = "mock"

    def generate_patch(self, request: ProviderRequest) -> PatchResponse:
        rendered = request.prompt.render()
        match = re.search(r"^### ([^\r\n]+)", rendered, re.MULTILINE)
        target = match.group(1).strip() if match else None
        old_line = _first_content_line(rendered)
        diff = (
            f"--- a/{target}\n"
            f"+++ b/{target}\n"
            "@@ -1 +1 @@\n"
            f"-{old_line}\n"
            f"+{old_line}\n"
        ) if target else ""
        return PatchResponse(
            unified_diff=diff,
            engineering_summary="Mock provider returned a deterministic no-op patch.",
            confidence=0.5,
            modified_files=(target,) if target else (),
            reasoning_summary="No API key was configured, so the offline provider exercised the patch pipeline.",
            provider_name=self.name,
        )


def _first_content_line(rendered_prompt: str) -> str:
    in_block = False
    for line in rendered_prompt.splitlines():
        if line.strip() == "```text":
            in_block = True
            continue
        if in_block and line.strip() == "```":
            break
        if in_block:
            return line
    return ""
