"""OpenRouter provider implementation."""

from __future__ import annotations

from dataclasses import dataclass

from engineering.providers.openai import OpenAIProvider


@dataclass(frozen=True, slots=True)
class OpenRouterProvider(OpenAIProvider):
    """OpenRouter uses an OpenAI-compatible chat completion API."""

    name: str = "openrouter"
    base_url: str = "https://openrouter.ai/api/v1/chat/completions"
