"""OpenAI-compatible provider implementation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.request import Request, urlopen

from engineering.models.core import PatchResponse, ProviderRequest
from engineering.providers.parsers import parse_patch_response


@dataclass(frozen=True, slots=True)
class OpenAIProvider:
    """Provider for OpenAI chat-compatible APIs."""

    api_key: str
    model: str | None = None
    name: str = "openai"
    base_url: str = "https://api.openai.com/v1/chat/completions"

    def generate_patch(self, request: ProviderRequest) -> PatchResponse:
        payload = {
            "model": request.model or self.model or "gpt-4.1-mini",
            "temperature": request.temperature,
            "messages": [
                {"role": "system", "content": request.prompt.system},
                {"role": "user", "content": request.prompt.render()},
            ],
        }
        http_request = Request(
            self.base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(http_request, timeout=120) as response:
            data = json.loads(response.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"]
        return parse_patch_response(content, provider_name=self.name)
