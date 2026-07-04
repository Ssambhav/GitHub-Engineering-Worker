"""Provider registry."""

from __future__ import annotations

from dataclasses import dataclass, field

from engineering.interfaces import AIProvider


@dataclass(slots=True)
class ProviderRegistry:
    """Runtime registry for AI providers."""

    _providers: dict[str, AIProvider] = field(default_factory=dict)

    def register(self, provider: AIProvider) -> None:
        self._providers[provider.name] = provider

    def get(self, name: str) -> AIProvider:
        return self._providers[name]

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._providers))
