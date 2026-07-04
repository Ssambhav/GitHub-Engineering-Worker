"""Discord webhook notification provider."""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import URLError
from urllib.request import Request, urlopen

from discord.models import DiscordEmbed
from notifications.models import Notification, NotificationResult


@dataclass(slots=True)
class DiscordWebhookProvider:
    """Sends optional rich notifications to Discord webhooks."""

    webhook_url: str | None
    username: str = "GitHub Engineering Worker"
    timeout_seconds: int = 10

    def send(self, notification: Notification) -> NotificationResult:
        if not self.webhook_url:
            return NotificationResult(False, "discord", "webhook is not configured")
        payload = self.format(notification)
        request = Request(
            self.webhook_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "github-engineering-worker"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                if response.status >= 400:
                    return NotificationResult(False, "discord", f"HTTP {response.status}")
        except URLError as exc:
            return NotificationResult(False, "discord", f"Discord unavailable: {exc.reason}")
        return NotificationResult(True, "discord", "sent")

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
        return {"username": self.username, "embeds": [embed.to_payload()]}


def _color(severity: str) -> int:
    if severity == "error":
        return 0xD73A49
    if severity == "warning":
        return 0xDBAB09
    if severity == "success":
        return 0x28A745
    return 0x0366D6
