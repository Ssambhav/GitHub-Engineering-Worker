"""Provider factory constrained to OpenClaw runtime defaults."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from engineering.configuration import EngineeringConfiguration
from engineering.interfaces import AIProvider
from engineering.providers.mock import MockProvider
from engineering.providers.openclaw import OpenClawCapabilityDetector, OpenClawProvider
from engineering.providers.registry import ProviderRegistry


@dataclass(slots=True)
class ProviderFactory:
    """Creates configured providers without global state."""

    config: EngineeringConfiguration
    environment: Mapping[str, str] | None = None

    def build_registry(self) -> ProviderRegistry:
        registry = ProviderRegistry()
        registry.register(MockProvider())
        openclaw_detection = OpenClawCapabilityDetector(
            cli=self.config.openclaw_cli,
            timeout_seconds=min(self.config.openclaw_timeout_seconds, 30),
        ).detect()
        if openclaw_detection.callable and openclaw_detection.configured:
            registry.register(
                OpenClawProvider(
                    cli=self.config.openclaw_cli,
                    model=self.config.model,
                    timeout_seconds=self.config.openclaw_timeout_seconds,
                    retries=self.config.openclaw_retries,
                    thinking=self.config.openclaw_thinking,
                )
            )
        return registry

    def select(self) -> AIProvider:
        registry = self.build_registry()
        if self.config.provider == "mock":
            return registry.get("mock")
        return registry.get("openclaw")
