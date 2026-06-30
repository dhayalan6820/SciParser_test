---
name: Browser screenshot architecture
description: Why direct Playwright CDP beats MCP browser_screenshot for live preview
---

## Rule
Always capture browser screenshots by connecting Playwright directly to Chrome
via `connect_over_cdp(cdp_url)` from brain.py. Never use the MCP
`browser_screenshot` tool for the live preview stream.

## Why
The MCP `browser_screenshot` tool screenshots the *initial* Chrome tab
(about:blank, 15836 bytes). browser-use creates its own context/page for
navigation; the initial tab is never updated. Result: every frame is identical.

## How to apply
- `mcp_manager.cdp_url` gives the Chrome CDP URL (e.g. `http://localhost:57225`)
- `pw.chromium.connect_over_cdp(cdp_url)` attaches to the running Chrome
- `browser.contexts[0].pages[-1]` is the most recently active page
- `page.screenshot(type="png", full_page=False)` → base64 → broadcast
- This is in `Brain._stream_browser_frames()` in `brain.py`
