"""Persistent Discord gateway runner for the worker bot."""

from __future__ import annotations

import argparse
import json
import os
import signal
import threading
import time
from typing import Any
from urllib.request import Request, urlopen

from websocket import WebSocketTimeoutException, create_connection

from discord.ai_worker import DiscordAIWorker
from discord.setup import API_BASE, GUILD_ID, TOKEN_ENV, slash_commands
from runtime.configuration.environment import load_environment
from worker.runtime_interface import WorkerRuntimeInterface


BASE_INTENTS = 1 | 512 | 4096
MESSAGE_CONTENT_INTENT = 32768


class WorkerDiscordBot:
    def __init__(self, token: str) -> None:
        self.token = token
        self.intents = BASE_INTENTS
        if os.environ.get("DISCORD_MESSAGE_CONTENT_INTENT", "").lower() in {"1", "true", "yes", "on"}:
            self.intents |= MESSAGE_CONTENT_INTENT
        self.sequence: int | None = None
        self.session_id: str | None = None
        self.user_id: str | None = None
        self.ws: Any = None
        self.running = True
        self.runtime = WorkerRuntimeInterface()
        self.worker = DiscordAIWorker()
        self._slash_messages = {item["name"]: item["name"].replace("-", " ") for item in slash_commands(self.runtime)}

    def run_forever(self) -> None:
        while self.running:
            try:
                self._connect_once()
            except KeyboardInterrupt:
                self.running = False
                raise
            except Exception as exc:
                close_status = getattr(self.ws, "close_status", None)
                close_reason = getattr(self.ws, "close_reason", None)
                print(
                    f"discord gateway disconnected: {exc}; close_status={close_status}; close_reason={close_reason}; reconnecting in 5s",
                    flush=True,
                )
                time.sleep(5)

    def _connect_once(self) -> None:
        gateway = self._request("/gateway/bot")
        self.ws = create_connection(
            f"{gateway['url']}?v=10&encoding=json",
            timeout=30,
            header=["User-Agent: github-engineering-worker"],
        )
        hello = self._recv_json()
        interval = hello["d"]["heartbeat_interval"] / 1000
        threading.Thread(target=self._heartbeat, args=(interval,), daemon=True).start()
        self._identify()
        while self.running:
            event = self._recv_json()
            self.sequence = event.get("s", self.sequence)
            op = event.get("op")
            if op == 7:
                raise RuntimeError("Discord requested reconnect")
            if op == 9:
                raise RuntimeError("Discord invalidated session")
            event_type = event.get("t")
            data = event.get("d") or {}
            if event_type == "READY":
                self.session_id = data["session_id"]
                self.user_id = data["user"]["id"]
                print(f"Discord bot online as {data['user']['username']}#{data['user']['discriminator']}", flush=True)
            elif event_type == "MESSAGE_CREATE":
                try:
                    self._handle_message(data)
                except Exception as exc:
                    print(f"discord message handling failed: {exc}", flush=True)
            elif event_type == "INTERACTION_CREATE":
                try:
                    self._handle_interaction(data)
                except Exception as exc:
                    print(f"discord interaction handling failed: {exc}", flush=True)

    def _identify(self) -> None:
        self.ws.send(
            json.dumps(
                {
                    "op": 2,
                    "d": {
                        "token": self.token,
                        "intents": self.intents,
                        "properties": {
                            "os": "windows",
                            "browser": "github-engineering-worker",
                            "device": "github-engineering-worker",
                        },
                    },
                }
            )
        )

    def _recv_json(self) -> dict[str, Any]:
        while True:
            try:
                raw = self.ws.recv()
            except WebSocketTimeoutException:
                continue
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="replace")
            if not raw:
                continue
            return json.loads(raw)

    def _heartbeat(self, interval: float) -> None:
        while self.running and self.ws is not None:
            time.sleep(interval)
            try:
                self.ws.send(json.dumps({"op": 1, "d": self.sequence}))
            except Exception:
                return

    def _handle_message(self, data: dict[str, Any]) -> None:
        author = data.get("author") or {}
        if author.get("bot"):
            return
        content = str(data.get("content") or "").strip()
        if content.startswith("/"):
            print("discord message ignored: slash command content handled by interaction flow", flush=True)
            return
        channel_id = str(data.get("channel_id"))
        mentions = {str(item.get("id")) for item in data.get("mentions", [])}
        mentioned = bool(self.user_id and self.user_id in mentions)
        if not content:
            print(f"discord message ignored: empty content channel={channel_id} mentioned={mentioned}", flush=True)
            return
        print(f"discord message received: channel={channel_id} mentioned={mentioned} chars={len(content)}", flush=True)
        if mentioned:
            content = self._strip_mention(content).strip()
        stop_typing = threading.Event()
        typing_thread = threading.Thread(target=self._typing_heartbeat, args=(channel_id, stop_typing), daemon=True)
        typing_thread.start()
        try:
            response = self.worker.respond(content, user_id=str(author.get("id") or ""), channel_id=channel_id)
        finally:
            stop_typing.set()
        self._send_message(channel_id, response)

    def _handle_interaction(self, data: dict[str, Any]) -> None:
        command = str((data.get("data") or {}).get("name") or "")
        response = self.worker.respond(self._slash_message(command), user_id=str((data.get("member") or {}).get("user", {}).get("id") or ""), channel_id=str(data.get("channel_id") or ""))
        self._request(
            f"/interactions/{data['id']}/{data['token']}/callback",
            method="POST",
            payload={"type": 4, "data": {"content": self._discord_content(response)}},
        )

    def _strip_mention(self, content: str) -> str:
        if not self.user_id:
            return content
        return content.replace(f"<@{self.user_id}>", "").replace(f"<@!{self.user_id}>", "")

    def _slash_message(self, command: str) -> str:
        return self._slash_messages.get(command, command.replace("-", " "))

    def _send_message(self, channel_id: str, content: str) -> None:
        self._request(f"/channels/{channel_id}/messages", method="POST", payload={"content": self._discord_content(content)})

    def _typing_heartbeat(self, channel_id: str, stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            try:
                self._request(f"/channels/{channel_id}/typing", method="POST")
            except Exception as exc:
                print(f"discord typing indicator failed: {exc}", flush=True)
                return
            stop_event.wait(8)

    def _discord_content(self, content: str) -> str:
        if len(content) <= 1900:
            return content
        return f"{content[:1900]}\n... output truncated ..."

    def _request(self, path: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> Any:
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
        with urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}


def main(argv: list[str] | None = None) -> int:
    load_environment()
    parser = argparse.ArgumentParser(description="Run the GitHub Engineering Worker Discord bot gateway.")
    parser.add_argument("--token-env", default=TOKEN_ENV)
    parser.add_argument("--guild-id", default=str(GUILD_ID))
    args = parser.parse_args(argv)
    token = os.environ.get(args.token_env)
    if not token:
        raise SystemExit(f"{args.token_env} is not configured")
    bot = WorkerDiscordBot(token)
    diagnostics = bot.runtime.startup_diagnostics()
    print("Discord runtime startup diagnostics:", flush=True)
    print(json.dumps(diagnostics, indent=2, sort_keys=True, default=str), flush=True)

    def _shutdown(*_args: object) -> None:
        bot.running = False
        if bot.ws is not None:
            try:
                bot.ws.close()
            except Exception:
                pass

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _shutdown)
        except ValueError:
            pass

    bot.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
