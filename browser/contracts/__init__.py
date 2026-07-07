"""Browser tool contract metadata."""

BROWSER_TOOL_ID = "browser.automation"

BROWSER_CAPABILITIES = (
    "browser.launch",
    "browser.close",
    "browser.navigate",
    "browser.tabs",
    "browser.wait",
    "browser.interact",
    "browser.read",
    "browser.search",
    "browser.vision",
    "browser.session",
)

__all__ = ["BROWSER_TOOL_ID", "BROWSER_CAPABILITIES"]
