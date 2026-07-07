"""Discord bot notification provider backed by the REST API."""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from discord.models import DiscordBotConfiguration, DiscordChannelPurpose, DiscordEmbed
from notifications.models import Notification, NotificationResult, NotificationType


API_BASE = "https://discord.com/api/v10"


NOTIFICATION_PURPOSES: dict[NotificationType, DiscordChannelPurpose] = {
    NotificationType.WORKER_STARTED: DiscordChannelPurpose.STARTUP,
    NotificationType.ISSUE_DETECTED: DiscordChannelPurpose.ISSUE_DETECTION,
    NotificationType.ISSUE_SOLVED: DiscordChannelPurpose.ISSUE_SOLVED,
    NotificationType.PULL_REQUEST_CREATED: DiscordChannelPurpose.PULL_REQUEST,
    NotificationType.RETRY_STARTED: DiscordChannelPurpose.PIPELINE_EXECUTION,
    NotificationType.RETRY_FAILED: DiscordChannelPurpose.RETRIES_EXHAUSTED,
    NotificationType.ESCALATION: DiscordChannelPurpose.MANUAL_INTERVENTION,
    NotificationType.WORKER_ERROR: DiscordChannelPurpose.ERRORS,
    NotificationType.HEALTH_WARNING: DiscordChannelPurpose.HEARTBEAT,
}


@dataclass(slots=True)
class DiscordBotProvider:
    """Sends routed worker notifications to Discord text channels."""

    token: str | None
    configuration: DiscordBotConfiguration
    timeout_seconds: int = 10

    def send(self, notification: Notification) -> NotificationResult:
        if not self.configuration.enabled:
            return NotificationResult(False, "discord_bot", "bot integration disabled")
        if not self.token:
            return NotificationResult(False, "discord_bot", f"{self.configuration.token_env} is not configured")
        purpose = NOTIFICATION_PURPOSES.get(notification.notification_type, DiscordChannelPurpose.HEARTBEAT)
        channel_id = self.configuration.channel_for(purpose)
        if not channel_id:
            return NotificationResult(False, "discord_bot", f"no Discord channel mapped for {purpose}")
        payload = self.format(notification)
        try:
            self._request(f"/channels/{quote(channel_id)}/messages", method="POST", payload=payload)
        except HTTPError as exc:
            return NotificationResult(False, "discord_bot", f"HTTP {exc.code}")
        except URLError as exc:
            return NotificationResult(False, "discord_bot", f"Discord unavailable: {exc.reason}")
        return NotificationResult(True, "discord_bot", "sent")

    def format(self, notification: Notification) -> dict[str, object]:
        embed = DiscordEmbed(
            title=notification.title,
            description=notification.message,
            color=_color(notification.severity),
            fields=tuple(
                {"name": str(key), "value": str(value), "inline": True}
                for key, value in notification.fields.items()
            ),
        )
        return {"embeds": [embed.to_payload()]}

    def _request(self, path: str, *, method: str = "GET", payload: dict[str, object] | None = None) -> object:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            f"{API_BASE}{path}",
            data=data,
            headers={
                "Authorization": f"Bot {self.token}",
                "Content-Type": "application/json",
                "User-Agent": "github-engineering-worker",
            },
            method=method,
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}


def _color(severity: str) -> int:
    if severity == "error":
        return 0xD73A49
    if severity == "warning":
        return 0xDBAB09
    if severity == "success":
        return 0x28A745
    return 0x0366D6
