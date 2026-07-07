"""Discord message models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class DiscordChannelPurpose(StrEnum):
    STARTUP = "startup"
    SHUTDOWN = "shutdown"
    HEARTBEAT = "heartbeat"
    ISSUE_DETECTION = "issue_detection"
    REPOSITORY_CLONING = "repository_cloning"
    PIPELINE_EXECUTION = "pipeline_execution"
    ISSUE_SOLVED = "issue_solved"
    COMMIT = "commit"
    PULL_REQUEST = "pull_request"
    RETRIES_EXHAUSTED = "retries_exhausted"
    LOW_CONFIDENCE = "low_confidence"
    MANUAL_INTERVENTION = "manual_intervention"
    ENGINEERING_REPORTS = "engineering_reports"
    AUDIT_SUMMARIES = "audit_summaries"
    ERRORS = "errors"
    EXCEPTIONS = "exceptions"
    QUEUE = "queue"
    PERFORMANCE = "performance"
    SUCCESS_RATE = "success_rate"
    SLASH_COMMANDS = "slash_commands"


@dataclass(frozen=True, slots=True)
class DiscordChannelRoute:
    channel: str
    purposes: tuple[DiscordChannelPurpose, ...]


@dataclass(frozen=True, slots=True)
class DiscordBotConfiguration:
    enabled: bool = False
    guild_id: str | None = None
    token_env: str = "DISCORD_BOT_TOKEN"
    auto_reconnect: bool = True
    slash_commands_enabled: bool = True
    channel_routes: tuple[DiscordChannelRoute, ...] = ()

    def channel_for(self, purpose: DiscordChannelPurpose) -> str | None:
        for route in self.channel_routes:
            if purpose in route.purposes:
                return route.channel
        return None


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
