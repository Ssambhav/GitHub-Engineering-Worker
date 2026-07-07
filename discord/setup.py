"""Discord guild setup, slash command registration, and validation."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from worker.runtime_interface import WorkerRuntimeInterface


GUILD_ID = 1523066948483682465
CLIENT_ID = 1523067975291240592
TOKEN_ENV = "DISCORD_BOT_TOKEN"
PERMISSIONS = 140123688016
SCOPES = ("bot", "applications.commands")
API_BASE = "https://discord.com/api/v10"

CATEGORY_CHANNELS: dict[str, tuple[str, ...]] = {
    "🤖 Worker Operations": ("worker-status", "worker-activity", "worker-success"),
    "👨‍💻 Engineering": ("developer-escalations", "engineering-reports"),
    "📊 Monitoring": ("worker-logs", "metrics"),
    "💬 Commands": ("commands",),
    "🔒 Admin": ("bot-testing", "admin"),
}

def invite_url(client_id: int = CLIENT_ID) -> str:
    query = urlencode(
        {
            "client_id": str(client_id),
            "permissions": str(PERMISSIONS),
            "scope": " ".join(SCOPES),
            "integration_type": "0",
        }
    )
    return f"https://discord.com/oauth2/authorize?{query}"


@dataclass(slots=True)
class DiscordSetupResult:
    categories: tuple[str, ...]
    channels: dict[str, str]
    commands: tuple[str, ...]
    gateway_connected: bool
    startup_message_sent: bool


def slash_commands(runtime: WorkerRuntimeInterface | None = None) -> tuple[dict[str, str], ...]:
    interface = runtime or WorkerRuntimeInterface()
    return interface.slash_commands()


class DiscordRestClient:
    def __init__(self, token: str, *, timeout_seconds: int = 15) -> None:
        self.token = token
        self.timeout_seconds = timeout_seconds

    def request(self, path: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> Any:
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


def setup_guild(token: str) -> DiscordSetupResult:
    client = DiscordRestClient(token)
    me = client.request("/users/@me")
    application_id = str(me["id"])
    guild = client.request(f"/guilds/{GUILD_ID}")
    channels_payload = client.request(f"/guilds/{GUILD_ID}/channels")
    by_name = {channel["name"]: channel for channel in channels_payload}

    categories: list[str] = []
    channels: dict[str, str] = {}
    for category_name, channel_names in CATEGORY_CHANNELS.items():
        category = by_name.get(category_name)
        if category is None:
            category = client.request(
                f"/guilds/{GUILD_ID}/channels",
                method="POST",
                payload={"name": category_name, "type": 4},
            )
            by_name[category_name] = category
        categories.append(category_name)
        for channel_name in channel_names:
            channel = by_name.get(channel_name)
            if channel is None:
                channel = client.request(
                    f"/guilds/{GUILD_ID}/channels",
                    method="POST",
                    payload={"name": channel_name, "type": 0, "parent_id": category["id"]},
                )
                by_name[channel_name] = channel
            elif channel.get("parent_id") != category["id"]:
                channel = client.request(
                    f"/channels/{channel['id']}",
                    method="PATCH",
                    payload={"parent_id": category["id"]},
                )
                by_name[channel_name] = channel
            channels[channel_name] = channel["id"]

    command_payloads = [{"name": item["name"], "description": item["description"], "type": 1} for item in slash_commands()]
    registered = client.request(
        f"/applications/{application_id}/guilds/{GUILD_ID}/commands",
        method="PUT",
        payload=command_payloads,
    )
    status_channel = by_name["worker-status"]
    client.request(
        f"/channels/{status_channel['id']}/messages",
        method="POST",
        payload={
            "embeds": [
                {
                    "title": "Worker Started",
                    "description": "GitHub Engineering Worker Discord integration is online.",
                    "color": 0x28A745,
                    "fields": [{"name": "Guild", "value": str(guild["id"]), "inline": True}],
                }
            ]
        },
    )
    return DiscordSetupResult(
        categories=tuple(categories),
        channels=channels,
        commands=tuple(command["name"] for command in registered),
        gateway_connected=validate_gateway(token),
        startup_message_sent=True,
    )


def validate_gateway(token: str) -> bool:
    from websocket import create_connection

    gateway = DiscordRestClient(token).request("/gateway/bot")
    url = f"{gateway['url']}?v=10&encoding=json"
    ws = create_connection(url, timeout=10)
    try:
        hello = json.loads(ws.recv())
        interval = hello.get("d", {}).get("heartbeat_interval")
        ws.send(json.dumps({"op": 1, "d": None}))
        ws.send(
            json.dumps(
                {
                    "op": 2,
                    "d": {
                        "token": token,
                        "intents": 33281,
                        "properties": {"os": "windows", "browser": "github-engineering-worker", "device": "github-engineering-worker"},
                    },
                }
            )
        )
        for _ in range(4):
            event = json.loads(ws.recv())
            if event.get("t") == "READY":
                return bool(interval)
        return False
    finally:
        ws.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Configure GitHub Engineering Worker Discord integration.")
    parser.add_argument("--invite-url", action="store_true", help="print the OAuth2 invite URL and exit")
    parser.add_argument("--apply", action="store_true", help="configure the authorized guild")
    parser.add_argument("--json", action="store_true", help="print machine-readable setup results")
    args = parser.parse_args(argv)
    if args.invite_url:
        print(invite_url())
        return 0
    if args.apply:
        token = os.environ.get(TOKEN_ENV)
        if not token:
            raise SystemExit(f"{TOKEN_ENV} is not configured")
        try:
            result = setup_guild(token)
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise SystemExit(f"Discord setup failed with HTTP {exc.code}: {detail}") from exc
        if args.json:
            print(json.dumps({"categories": list(result.categories), "channels": result.channels, "commands": list(result.commands), "gateway_connected": result.gateway_connected, "startup_message_sent": result.startup_message_sent}, indent=2, sort_keys=True))
        else:
            print(result)
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
