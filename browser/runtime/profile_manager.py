"""Worker-owned browser profile management."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from browser.exceptions import BrowserRuntimeError


@dataclass(frozen=True, slots=True)
class BrowserProfileState:
    profile_path: Path
    browser_type: str
    browser_channel: str | None
    executable_path: Path | None
    setup_required: bool
    authentication_required: bool


class BrowserProfileManager:
    """Resolves persistent automation profiles without touching personal profiles."""

    PERSONAL_PROFILE_MARKERS = ("Opera Software", "Google\\Chrome\\User Data", "Microsoft\\Edge\\User Data")

    def __init__(self, profiles_root: Path = Path("runtime") / "browser_profiles") -> None:
        self.profiles_root = profiles_root

    def resolve(
        self,
        *,
        profile_name: str,
        requested_profile_path: Path | None,
        browser_type: str,
        setup_mode: bool,
        require_authenticated_profile: bool,
    ) -> BrowserProfileState:
        profile_path = self._profile_path(profile_name, requested_profile_path)
        setup_required = not profile_path.exists()
        profile_path.mkdir(parents=True, exist_ok=True)
        auth_required = require_authenticated_profile and not self._has_auth_state(profile_path)
        if setup_required or setup_mode:
            self._write_state(profile_path, browser_type, "setup_required")
        elif auth_required:
            self._write_state(profile_path, browser_type, "authentication_required")
        return BrowserProfileState(
            profile_path=profile_path,
            browser_type=self._playwright_browser_type(browser_type),
            browser_channel=self._browser_channel(browser_type),
            executable_path=self._opera_executable() if browser_type == "opera" else None,
            setup_required=setup_required,
            authentication_required=auth_required,
        )

    def record_authenticated(self, profile_path: Path, browser_type: str) -> None:
        self._write_state(profile_path, browser_type, "authenticated")

    def _profile_path(self, profile_name: str, requested: Path | None) -> Path:
        path = requested or self.profiles_root / profile_name
        resolved = path.resolve()
        lowered = str(resolved).lower()
        if any(marker.lower() in lowered for marker in self.PERSONAL_PROFILE_MARKERS):
            raise BrowserRuntimeError(f"refusing to use a personal browser profile: {resolved}")
        return resolved

    def _has_auth_state(self, profile_path: Path) -> bool:
        state_file = profile_path / "worker-profile-state.json"
        if state_file.exists():
            try:
                return json.loads(state_file.read_text(encoding="utf-8")).get("state") == "authenticated"
            except json.JSONDecodeError:
                return False
        return any((profile_path / name).exists() for name in ("Cookies", "Local Storage", "Network"))

    def _write_state(self, profile_path: Path, browser_type: str, state: str) -> None:
        payload = {"browser_type": browser_type, "state": state, "updated_at": datetime.now(UTC).isoformat()}
        (profile_path / "worker-profile-state.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def _playwright_browser_type(self, browser_type: str) -> str:
        return "chromium" if browser_type in {"chrome", "edge", "opera"} else browser_type

    def _browser_channel(self, browser_type: str) -> str | None:
        return {"chrome": "chrome", "edge": "msedge"}.get(browser_type)

    def _opera_executable(self) -> Path | None:
        candidates = [
            os.environ.get("OPERA_EXECUTABLE"),
            r"C:\Users\HP\AppData\Local\Programs\Opera\opera.exe",
            r"C:\Program Files\Opera\opera.exe",
            r"C:\Program Files (x86)\Opera\opera.exe",
        ]
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return Path(candidate)
        return None
