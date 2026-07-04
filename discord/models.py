"""Discord message models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class DiscordEmbed:
    title: str
    description: str
    color: int
    fields: tuple[dict[str, Any], ...] = ()

    def to_payload(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "color": self.color,
            "fields": list(self.fields),
        }
