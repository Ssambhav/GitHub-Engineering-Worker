"""Typed configuration for browser automation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class BrowserConfiguration:
    """Runtime defaults and safety controls for Playwright browser sessions."""

    browser_type: str = "chromium"
    browser_channel: str | None = None
    executable_path: Path | None = None
    headless: bool = True
    navigation_timeout_ms: int = 30_000
    action_timeout_ms: int = 15_000
    viewport_width: int = 1280
    viewport_height: int = 720
    downloads_path: Path | None = None
    artifacts_path: Path | None = None
    persistent_profile_path: Path | None = None
    profile_name: str = "default"
    profiles_root: Path = Path("runtime") / "browser_profiles"
    setup_mode: bool = False
    require_authenticated_profile: bool = False
    allowed_domains: tuple[str, ...] = ()
    blocked_domains: tuple[str, ...] = ()
    allowed_download_extensions: tuple[str, ...] = ()
    accept_downloads: bool = True
    popup_handling: str = "allow"
    unexpected_dialog_action: str = "dismiss"
    extra_launch_args: tuple[str, ...] = field(default_factory=tuple)

    def validate(self) -> None:
        if self.browser_type not in {"chromium", "firefox", "webkit", "chrome", "edge", "opera"}:
            raise ValueError(f"unsupported browser type: {self.browser_type}")
        if self.navigation_timeout_ms <= 0:
            raise ValueError("navigation_timeout_ms must be positive")
        if self.action_timeout_ms <= 0:
            raise ValueError("action_timeout_ms must be positive")
        if self.viewport_width <= 0 or self.viewport_height <= 0:
            raise ValueError("viewport dimensions must be positive")
        if self.popup_handling not in {"allow", "block"}:
            raise ValueError("popup_handling must be allow or block")
        if self.unexpected_dialog_action not in {"accept", "dismiss"}:
            raise ValueError("unexpected_dialog_action must be accept or dismiss")
