"""Provider factory with environment-aware fallback."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

from engineering.configuration import EngineeringConfiguration
from engineering.interfaces import AIProvider
from engineering.providers.mock import MockProvider
from engineering.providers.openai import OpenAIProvider
from engineering.providers.openrouter import OpenRouterProvider
from engineering.providers.registry import ProviderRegistry


@dataclass(slots=True)
class ProviderFactory:
    """Creates configured providers without global state."""

    config: EngineeringConfiguration
    environment: Mapping[str, str] | None = None

    def build_registry(self) -> ProviderRegistry:
        env = self.environment or os.environ
        registry = ProviderRegistry()
        registry.register(MockProvider())
        if env.get(self.config.openai_api_key_env):
            registry.register(OpenAIProvider(api_key=env[self.config.openai_api_key_env], model=self.config.model))
        if env.get(self.config.openrouter_api_key_env):
            registry.register(OpenRouterProvider(api_key=env[self.config.openrouter_api_key_env], model=self.config.model))
        return registry

    def select(self) -> AIProvider:
        registry = self.build_registry()
        if self.config.provider == "auto":
            for name in ("openai", "openrouter", "codex", "mock"):
                if name in registry.names():
                    return registry.get(name)
        return registry.get(self.config.provider)
