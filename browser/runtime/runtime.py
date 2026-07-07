"""Playwright-backed generic browser automation runtime."""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import replace
from html.parser import HTMLParser
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Mapping
from urllib.parse import urlparse
from uuid import uuid4

from playwright.sync_api import Browser, BrowserContext, Error as PlaywrightError, Page, Playwright, sync_playwright

from browser.configuration import BrowserConfiguration
from browser.exceptions import BrowserConfigurationError, BrowserRuntimeError, BrowserSafetyError
from browser.models import BrowserActionResult, BrowserArtifact
from browser.runtime.profile_manager import BrowserProfileManager


class _MarkdownExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.href: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = dict(attrs)
        if tag in {"p", "div", "section", "article", "tr", "ul", "ol"}:
            self.parts.append("\n")
        elif tag in {"h1", "h2", "h3"}:
            self.parts.append("\n" + "#" * int(tag[1]) + " ")
        elif tag == "li":
            self.parts.append("\n- ")
        elif tag == "a":
            self.href = attrs_map.get("href")

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self.href = None
        if tag in {"p", "div", "section", "article", "tr", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if not text:
            return
        if self.href:
            self.parts.append(f"[{text}]({self.href})")
        else:
            self.parts.append(text + " ")

    def markdown(self) -> str:
        return re.sub(r"\n{3,}", "\n\n", "".join(self.parts)).strip()


class BrowserRuntime:
    """Reusable Playwright runtime for generic browser automation."""

    def __init__(self, configuration: BrowserConfiguration | None = None) -> None:
        self.configuration = configuration or BrowserConfiguration()
        self.configuration.validate()
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._profile_manager = BrowserProfileManager(self.configuration.profiles_root)
        self._pages: dict[str, Page] = {}
        self._active_tab_id: str | None = None

    def perform(self, action: str, inputs: Mapping[str, Any]) -> BrowserActionResult:
        started = perf_counter()
        try:
            result = self._perform(action, inputs)
            return replace(result, execution_time_ms=int((perf_counter() - started) * 1000))
        except Exception as exc:
            page = self._active_page_or_none()
            return BrowserActionResult(
                success=False,
                action=action,
                execution_time_ms=int((perf_counter() - started) * 1000),
                url=page.url if page else "",
                page_title=self._safe_title(page),
                errors=(str(exc),),
            )

    def _perform(self, action: str, inputs: Mapping[str, Any]) -> BrowserActionResult:
        handlers: dict[str, Callable[[Mapping[str, Any]], BrowserActionResult]] = {
            "launch": self.launch,
            "close": lambda _: self.shutdown(),
            "open_url": self.open_url,
            "go_back": lambda _: self._page_action("go_back", lambda page: page.go_back()),
            "go_forward": lambda _: self._page_action("go_forward", lambda page: page.go_forward()),
            "refresh": lambda _: self._page_action("refresh", lambda page: page.reload()),
            "new_tab": self.new_tab,
            "close_tab": self.close_tab,
            "switch_tab": self.switch_tab,
            "wait_for_element": self.wait_for_element,
            "wait_for_network_idle": lambda _: self._page_action(
                "wait_for_network_idle", lambda page: page.wait_for_load_state("networkidle")
            ),
            "click": lambda data: self._locator_action("click", data, lambda locator: locator.click()),
            "double_click": lambda data: self._locator_action("double_click", data, lambda locator: locator.dblclick()),
            "hover": lambda data: self._locator_action("hover", data, lambda locator: locator.hover()),
            "type": self.type_text,
            "fill": lambda data: self._locator_action("fill", data, lambda locator: locator.fill(str(data["text"]))),
            "press_key": self.press_key,
            "scroll": self.scroll,
            "drag": self.drag,
            "select_dropdown": self.select_dropdown,
            "upload_file": self.upload_file,
            "download_file": self.download_file,
            "read_visible_text": lambda _: self._read("read_visible_text", lambda page: page.locator("body").inner_text()),
            "read_page_title": lambda _: self._read("read_page_title", lambda page: page.title()),
            "read_links": self.read_links,
            "read_buttons": self.read_buttons,
            "read_forms": self.read_forms,
            "read_tables": self.read_tables,
            "extract_html": lambda _: self._read("extract_html", lambda page: page.content()),
            "extract_markdown": self.extract_markdown,
            "extract_dom": self.extract_dom,
            "find_by_text": lambda data: self._find("find_by_text", self._page().get_by_text(str(data["text"]))),
            "find_by_css": lambda data: self._find("find_by_css", self._page().locator(str(data["selector"]))),
            "find_by_xpath": lambda data: self._find("find_by_xpath", self._page().locator(f"xpath={data['xpath']}")),
            "find_by_role": self.find_by_role,
            "find_by_label": lambda data: self._find("find_by_label", self._page().get_by_label(str(data["label"]))),
            "find_by_placeholder": lambda data: self._find(
                "find_by_placeholder", self._page().get_by_placeholder(str(data["placeholder"]))
            ),
            "take_screenshot": self.take_screenshot,
            "full_page_screenshot": lambda data: self.take_screenshot({**data, "full_page": True}),
            "element_screenshot": self.element_screenshot,
            "page_dimensions": self.page_dimensions,
            "set_viewport": self.set_viewport,
            "get_storage": self.get_storage,
            "set_cookies": self.set_cookies,
            "mark_authenticated": self.mark_authenticated,
        }
        try:
            return handlers[action](inputs)
        except KeyError as exc:
            raise BrowserRuntimeError(f"unsupported browser action: {action}") from exc
        except PlaywrightError as exc:
            if "Executable doesn't exist" in str(exc) or "Looks like Playwright was just installed" in str(exc):
                self._install_browser()
                self._reset()
                return handlers[action](inputs)
            raise

    def launch(self, inputs: Mapping[str, Any]) -> BrowserActionResult:
        self.configuration = self._configuration_from_inputs(inputs)
        self.configuration.validate()
        self._ensure_started()
        page = self._page()
        return self._result("launch", page, {"browser_type": self.configuration.browser_type, "tabs": tuple(self._pages)})

    def shutdown(self) -> BrowserActionResult:
        page = self._active_page_or_none()
        self._reset()
        return BrowserActionResult(
            success=True,
            action="close",
            execution_time_ms=0,
            url=page.url if page else "",
            page_title=self._safe_title(page),
            data={"closed": True},
        )

    def open_url(self, inputs: Mapping[str, Any]) -> BrowserActionResult:
        url = str(inputs["url"])
        self._assert_url_allowed(url)
        page = self._page()
        page.goto(url, wait_until=str(inputs.get("wait_until", "load")))
        return self._result("open_url", page)

    def new_tab(self, inputs: Mapping[str, Any]) -> BrowserActionResult:
        context = self._browser_context()
        page = context.new_page()
        tab_id = self._register_page(page)
        if "url" in inputs:
            self._assert_url_allowed(str(inputs["url"]))
            page.goto(str(inputs["url"]))
        return self._result("new_tab", page, {"tab_id": tab_id, "tabs": tuple(self._pages)})

    def close_tab(self, inputs: Mapping[str, Any]) -> BrowserActionResult:
        tab_id = str(inputs.get("tab_id") or self._active_tab_id)
        page = self._pages.pop(tab_id)
        url = page.url
        title = self._safe_title(page)
        page.close()
        self._active_tab_id = next(iter(self._pages), None)
        if not self._pages:
            self._register_page(self._browser_context().new_page())
        return BrowserActionResult(True, "close_tab", 0, url=url, page_title=title, data={"tab_id": tab_id})

    def switch_tab(self, inputs: Mapping[str, Any]) -> BrowserActionResult:
        tab_id = str(inputs["tab_id"])
        if tab_id not in self._pages:
            raise BrowserRuntimeError(f"unknown tab_id: {tab_id}")
        self._active_tab_id = tab_id
        page = self._page()
        page.bring_to_front()
        return self._result("switch_tab", page, {"tab_id": tab_id})

    def wait_for_element(self, inputs: Mapping[str, Any]) -> BrowserActionResult:
        selector = str(inputs["selector"])
        state = str(inputs.get("state", "visible"))
        timeout = int(inputs.get("timeout_ms", self.configuration.action_timeout_ms))
        self._page().wait_for_selector(selector, state=state, timeout=timeout)
        return self._result("wait_for_element", self._page(), {"selector": selector, "state": state})

    def type_text(self, inputs: Mapping[str, Any]) -> BrowserActionResult:
        locator = self._locator(inputs)
        locator.type(str(inputs["text"]), delay=int(inputs.get("delay_ms", 0)))
        return self._result("type", self._page())

    def press_key(self, inputs: Mapping[str, Any]) -> BrowserActionResult:
        key = str(inputs["key"])
        if "selector" in inputs:
            self._locator(inputs).press(key)
        else:
            self._page().keyboard.press(key)
        return self._result("press_key", self._page(), {"key": key})

    def scroll(self, inputs: Mapping[str, Any]) -> BrowserActionResult:
        x = int(inputs.get("x", 0))
        y = int(inputs.get("y", 0))
        self._page().mouse.wheel(x, y)
        return self._result("scroll", self._page(), {"x": x, "y": y})

    def drag(self, inputs: Mapping[str, Any]) -> BrowserActionResult:
        source = self._page().locator(str(inputs["source_selector"])).first
        target = self._page().locator(str(inputs["target_selector"])).first
        source.drag_to(target)
        return self._result("drag", self._page())

    def select_dropdown(self, inputs: Mapping[str, Any]) -> BrowserActionResult:
        selected = self._locator(inputs).select_option(str(inputs["value"]))
        return self._result("select_dropdown", self._page(), {"selected": tuple(selected)})

    def upload_file(self, inputs: Mapping[str, Any]) -> BrowserActionResult:
        path = Path(str(inputs["path"])).resolve()
        if not path.exists():
            raise BrowserRuntimeError(f"upload file does not exist: {path}")
        self._locator(inputs).set_input_files(str(path))
        return self._result("upload_file", self._page(), {"path": str(path)})

    def download_file(self, inputs: Mapping[str, Any]) -> BrowserActionResult:
        page = self._page()
        with page.expect_download() as download_info:
            if "selector" in inputs:
                self._locator(inputs).click()
            elif "url" in inputs:
                self._assert_url_allowed(str(inputs["url"]))
                page.goto(str(inputs["url"]))
            else:
                raise BrowserRuntimeError("download_file requires selector or url")
        download = download_info.value
        suggested = download.suggested_filename
        self._assert_download_allowed(suggested)
        downloads_path = self._downloads_path()
        target = downloads_path / suggested
        download.save_as(str(target))
        artifact = BrowserArtifact("browser-download", "download", str(target), {"filename": suggested})
        return self._result("download_file", page, {"filename": suggested}, artifacts=(artifact,))

    def read_links(self, _: Mapping[str, Any]) -> BrowserActionResult:
        data = self._page().eval_on_selector_all(
            "a",
            "(els) => els.map((a) => ({text: a.innerText, href: a.href, title: a.title}))",
        )
        return self._result("read_links", self._page(), {"links": data})

    def read_buttons(self, _: Mapping[str, Any]) -> BrowserActionResult:
        data = self._page().eval_on_selector_all(
            "button, input[type=button], input[type=submit]",
            "(els) => els.map((b) => ({text: b.innerText || b.value || '', type: b.type || '', disabled: b.disabled}))",
        )
        return self._result("read_buttons", self._page(), {"buttons": data})

    def read_forms(self, _: Mapping[str, Any]) -> BrowserActionResult:
        data = self._page().eval_on_selector_all(
            "form",
            """(forms) => forms.map((form) => ({
                action: form.action, method: form.method,
                fields: Array.from(form.querySelectorAll('input, textarea, select')).map((f) => ({
                    name: f.name || '', type: f.type || f.tagName.toLowerCase(),
                    label: f.labels && f.labels[0] ? f.labels[0].innerText : '',
                    placeholder: f.placeholder || ''
                }))
            }))""",
        )
        return self._result("read_forms", self._page(), {"forms": data})

    def read_tables(self, _: Mapping[str, Any]) -> BrowserActionResult:
        data = self._page().eval_on_selector_all(
            "table",
            """(tables) => tables.map((table) => Array.from(table.rows).map(
                (row) => Array.from(row.cells).map((cell) => cell.innerText)
            ))""",
        )
        return self._result("read_tables", self._page(), {"tables": data})

    def extract_markdown(self, _: Mapping[str, Any]) -> BrowserActionResult:
        parser = _MarkdownExtractor()
        parser.feed(self._page().content())
        return self._result("extract_markdown", self._page(), {"markdown": parser.markdown()})

    def extract_dom(self, _: Mapping[str, Any]) -> BrowserActionResult:
        dom = self._page().eval_on_selector(
            "body",
            """(body) => ({
                tag: body.tagName.toLowerCase(),
                text: body.innerText,
                children: Array.from(body.children).map((el) => ({
                    tag: el.tagName.toLowerCase(),
                    id: el.id || '',
                    classes: el.className || '',
                    text: (el.innerText || '').slice(0, 500)
                }))
            })""",
        )
        return self._result("extract_dom", self._page(), {"dom": dom})

    def find_by_role(self, inputs: Mapping[str, Any]) -> BrowserActionResult:
        kwargs: dict[str, Any] = {}
        if "name" in inputs:
            kwargs["name"] = str(inputs["name"])
        return self._find("find_by_role", self._page().get_by_role(str(inputs["role"]), **kwargs))

    def take_screenshot(self, inputs: Mapping[str, Any]) -> BrowserActionResult:
        page = self._page()
        path = self._artifact_path(str(inputs.get("path") or f"screenshot-{uuid4().hex}.png"))
        page.screenshot(path=str(path), full_page=bool(inputs.get("full_page", False)))
        artifact = BrowserArtifact("browser-screenshot", "screenshot", str(path), {"full_page": bool(inputs.get("full_page"))})
        return self._result("take_screenshot", page, screenshots=(artifact,))

    def element_screenshot(self, inputs: Mapping[str, Any]) -> BrowserActionResult:
        path = self._artifact_path(str(inputs.get("path") or f"element-{uuid4().hex}.png"))
        self._locator(inputs).screenshot(path=str(path))
        artifact = BrowserArtifact("browser-element-screenshot", "screenshot", str(path), {"selector": inputs.get("selector")})
        return self._result("element_screenshot", self._page(), screenshots=(artifact,))

    def page_dimensions(self, _: Mapping[str, Any]) -> BrowserActionResult:
        data = self._page().evaluate(
            """() => ({
                width: document.documentElement.scrollWidth,
                height: document.documentElement.scrollHeight,
                viewportWidth: window.innerWidth,
                viewportHeight: window.innerHeight,
                deviceScaleFactor: window.devicePixelRatio
            })"""
        )
        return self._result("page_dimensions", self._page(), data)

    def set_viewport(self, inputs: Mapping[str, Any]) -> BrowserActionResult:
        width = int(inputs["width"])
        height = int(inputs["height"])
        self._page().set_viewport_size({"width": width, "height": height})
        return self._result("set_viewport", self._page(), {"width": width, "height": height})

    def get_storage(self, _: Mapping[str, Any]) -> BrowserActionResult:
        page = self._page()
        local_storage = self._safe_storage(page, "localStorage")
        session_storage = self._safe_storage(page, "sessionStorage")
        return self._result(
            "get_storage",
            page,
            {"cookies": self._browser_context().cookies(), "local_storage": local_storage, "session_storage": session_storage},
        )

    def set_cookies(self, inputs: Mapping[str, Any]) -> BrowserActionResult:
        cookies = list(inputs.get("cookies", ()))
        self._browser_context().add_cookies(cookies)
        return self._result("set_cookies", self._page(), {"cookies_added": len(cookies)})

    def mark_authenticated(self, _: Mapping[str, Any]) -> BrowserActionResult:
        self._profile_manager.record_authenticated(self.configuration.persistent_profile_path or self.configuration.profiles_root / self.configuration.profile_name, self.configuration.browser_type)
        return self._result("mark_authenticated", self._page(), {"profile_authenticated": True})

    def _page_action(self, action: str, callback: Callable[[Page], Any]) -> BrowserActionResult:
        page = self._page()
        callback(page)
        return self._result(action, page)

    def _locator_action(self, action: str, inputs: Mapping[str, Any], callback: Callable[[Any], Any]) -> BrowserActionResult:
        callback(self._locator(inputs))
        return self._result(action, self._page())

    def _read(self, action: str, callback: Callable[[Page], Any]) -> BrowserActionResult:
        value = callback(self._page())
        return self._result(action, self._page(), {"value": value})

    def _safe_storage(self, page: Page, storage_name: str) -> Mapping[str, Any]:
        try:
            return page.evaluate(f"() => Object.fromEntries(Object.entries({storage_name}))")
        except PlaywrightError:
            return {}

    def _find(self, action: str, locator: Any) -> BrowserActionResult:
        count = locator.count()
        matches = []
        for index in range(min(count, 25)):
            item = locator.nth(index)
            matches.append(
                {
                    "index": index,
                    "text": item.inner_text(timeout=1_000) if item.is_visible(timeout=1_000) else "",
                    "visible": item.is_visible(timeout=1_000),
                }
            )
        return self._result(action, self._page(), {"count": count, "matches": tuple(matches)})

    def _ensure_started(self) -> None:
        if self._playwright is None:
            self._playwright = sync_playwright().start()
        if self._context is not None and self._active_page_or_none() is not None:
            return
        profile_state = self._profile_manager.resolve(
            profile_name=self.configuration.profile_name,
            requested_profile_path=self.configuration.persistent_profile_path,
            browser_type=self.configuration.browser_type,
            setup_mode=self.configuration.setup_mode,
            require_authenticated_profile=self.configuration.require_authenticated_profile,
        )
        self.configuration = replace(
            self.configuration,
            browser_type=profile_state.browser_type,
            browser_channel=profile_state.browser_channel or self.configuration.browser_channel,
            executable_path=profile_state.executable_path or self.configuration.executable_path,
            persistent_profile_path=profile_state.profile_path,
        )
        if profile_state.authentication_required and not self.configuration.setup_mode:
            raise BrowserRuntimeError("browser authentication required; run setup mode and notify operations")
        browser_launcher = getattr(self._playwright, self.configuration.browser_type)
        launch_options = {
            "headless": self.configuration.headless,
            "accept_downloads": self.configuration.accept_downloads,
            "downloads_path": str(self._downloads_path()),
            "viewport": {"width": self.configuration.viewport_width, "height": self.configuration.viewport_height},
            "args": list(self.configuration.extra_launch_args),
        }
        if self.configuration.browser_channel:
            launch_options["channel"] = self.configuration.browser_channel
        if self.configuration.executable_path:
            launch_options["executable_path"] = str(self.configuration.executable_path)
        if self.configuration.persistent_profile_path:
            profile = self.configuration.persistent_profile_path
            self._context = browser_launcher.launch_persistent_context(
                str(profile),
                **launch_options,
            )
        else:
            raise BrowserRuntimeError("browser automation requires a worker-owned persistent profile")
        self._context.set_default_navigation_timeout(self.configuration.navigation_timeout_ms)
        self._context.set_default_timeout(self.configuration.action_timeout_ms)
        self._context.on("page", self._handle_new_page)
        self._context.on("dialog", self._handle_dialog)
        if not self._context.pages:
            self._context.new_page()
        for page in self._context.pages:
            if page not in self._pages.values():
                self._register_page(page)

    def _browser_context(self) -> BrowserContext:
        self._ensure_started()
        if self._context is None:
            raise BrowserRuntimeError("browser context is not available")
        return self._context

    def _page(self) -> Page:
        self._ensure_started()
        page = self._active_page_or_none()
        if page is None:
            raise BrowserRuntimeError("active page is not available")
        return page

    def _active_page_or_none(self) -> Page | None:
        if self._active_tab_id is None:
            return None
        page = self._pages.get(self._active_tab_id)
        if page is None or page.is_closed():
            return None
        return page

    def _register_page(self, page: Page) -> str:
        tab_id = uuid4().hex
        self._pages[tab_id] = page
        self._active_tab_id = tab_id
        page.on("crash", lambda _: self._recover_from_crash(tab_id))
        page.on("popup", lambda popup: self._handle_popup(popup))
        return tab_id

    def _handle_new_page(self, page: Page) -> None:
        if self.configuration.popup_handling == "block":
            page.close()
            return
        self._register_page(page)

    def _handle_popup(self, page: Page) -> None:
        if self.configuration.popup_handling == "block":
            page.close()

    def _handle_dialog(self, dialog: Any) -> None:
        if self.configuration.unexpected_dialog_action == "accept":
            dialog.accept()
        else:
            dialog.dismiss()

    def _recover_from_crash(self, tab_id: str) -> None:
        self._pages.pop(tab_id, None)
        self._active_tab_id = next(iter(self._pages), None)

    def _reset(self) -> None:
        for page in tuple(self._pages.values()):
            if not page.is_closed():
                page.close()
        self._pages.clear()
        self._active_tab_id = None
        if self._context is not None:
            self._context.close()
        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()
        self._playwright = None
        self._browser = None
        self._context = None

    def _configuration_from_inputs(self, inputs: Mapping[str, Any]) -> BrowserConfiguration:
        config = self.configuration
        updates: dict[str, Any] = {}
        for key in (
            "browser_type",
            "headless",
            "navigation_timeout_ms",
            "action_timeout_ms",
            "viewport_width",
            "viewport_height",
            "allowed_domains",
            "blocked_domains",
            "allowed_download_extensions",
            "accept_downloads",
            "popup_handling",
            "unexpected_dialog_action",
            "browser_channel",
            "profile_name",
            "setup_mode",
            "require_authenticated_profile",
        ):
            if key in inputs:
                value = inputs[key]
                if key.endswith("domains") or key == "allowed_download_extensions":
                    value = tuple(str(item) for item in value)
                updates[key] = value
        for key in ("downloads_path", "artifacts_path", "persistent_profile_path", "profiles_root", "executable_path"):
            if key in inputs and inputs[key]:
                updates[key] = Path(str(inputs[key]))
        try:
            return replace(config, **updates)
        except TypeError as exc:
            raise BrowserConfigurationError(str(exc)) from exc

    def _locator(self, inputs: Mapping[str, Any]) -> Any:
        selector = str(inputs["selector"])
        return self._page().locator(selector).first

    def _assert_url_allowed(self, url: str) -> None:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        if parsed.scheme not in {"http", "https", "file", "about"}:
            raise BrowserSafetyError(f"blocked unsupported URL scheme: {parsed.scheme}")
        if self.configuration.allowed_domains and not self._host_matches(host, self.configuration.allowed_domains):
            raise BrowserSafetyError(f"domain is not allowed: {host}")
        if self._host_matches(host, self.configuration.blocked_domains):
            raise BrowserSafetyError(f"domain is blocked: {host}")

    def _assert_download_allowed(self, filename: str) -> None:
        extensions = self.configuration.allowed_download_extensions
        if extensions and Path(filename).suffix.lower() not in {ext.lower() for ext in extensions}:
            raise BrowserSafetyError(f"download extension is not allowed: {filename}")

    def _host_matches(self, host: str, patterns: tuple[str, ...]) -> bool:
        return any(host == pattern or host.endswith("." + pattern.lstrip(".")) for pattern in patterns)

    def _artifact_path(self, filename: str) -> Path:
        root = self.configuration.artifacts_path or Path("runtime") / "tmp" / "browser"
        root.mkdir(parents=True, exist_ok=True)
        path = (root / filename).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _downloads_path(self) -> Path:
        path = self.configuration.downloads_path or Path("runtime") / "tmp" / "browser" / "downloads"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _install_browser(self) -> None:
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", self.configuration.browser_type],
            check=True,
            capture_output=True,
            text=True,
        )

    def _safe_title(self, page: Page | None) -> str:
        if page is None or page.is_closed():
            return ""
        try:
            return page.title()
        except PlaywrightError:
            return ""

    def _result(
        self,
        action: str,
        page: Page,
        data: Mapping[str, Any] | None = None,
        artifacts: tuple[BrowserArtifact, ...] = (),
        screenshots: tuple[BrowserArtifact, ...] = (),
    ) -> BrowserActionResult:
        return BrowserActionResult(
            success=True,
            action=action,
            execution_time_ms=0,
            url=page.url,
            page_title=self._safe_title(page),
            data=data or {},
            artifacts=artifacts,
            screenshots=screenshots,
        )
