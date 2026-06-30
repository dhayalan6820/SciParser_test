---
name: Chrome CDP subprocess pattern
description: How to start Chrome so CDP is TCP-accessible for browser-use and Playwright in Replit
---

## Rule
Always start Chrome via `asyncio.create_subprocess_exec` (not `playwright.chromium.launch()`) when the CDP port needs to be TCP-accessible (e.g. for browser-use's BrowserSession to connect via cdp_url).

**Why:** `playwright.launch()` uses an internal pipe (`--remote-debugging-pipe`), so even if you pass `--remote-debugging-port=PORT` in `args`, the TCP port is NOT reliably accessible via `http://localhost:PORT`. browser-use's `BrowserSession.connect(cdp_url)` needs an HTTP-accessible CDP endpoint and will timeout/fail with the pipe approach.

**How to apply:**
1. Find Chrome binary — in Replit it lives at `{workspace}/.cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell` (workspace dir, NOT `~/.cache`).
2. `asyncio.create_subprocess_exec(chrome_binary, f'--remote-debugging-port={port}', ...)`
3. Poll `http://localhost:{port}/json/version` via aiohttp until status 200.
4. Then `playwright.chromium.connect_over_cdp(cdp_url)` — this works fine over TCP.
5. Write browser-use config.json with `{"browser_profile": {"default": {"id": "default", "cdp_url": ..., ...}}}` — the `"id"` field is required by `BrowserProfileEntry`.
6. Set `BROWSER_USE_CONFIG_DIR` env var before starting the MCP server.

## Verified working
Smoke test confirmed: Chrome subprocess starts, CDP ready on TCP, Playwright `connect_over_cdp()` connects successfully.
