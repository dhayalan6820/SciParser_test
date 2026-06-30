---
name: Chrome CDP subprocess pattern
description: How to start Chrome with TCP-accessible CDP for browser-use in Replit; correct config format
---

## Rule: start Chrome via subprocess, not playwright.launch()
Use `asyncio.create_subprocess_exec` so Chrome listens on TCP.
`playwright.launch()` uses `--remote-debugging-pipe` internally; the TCP port is NOT reliably accessible even with `--remote-debugging-port` in args.

**Why:** browser-use's `BrowserSession.connect(cdp_url)` polls `http://localhost:PORT` via HTTP. If Chrome only has a pipe connection the HTTP endpoint is absent, the 15s timeout fires, BrowserSession stays uninitialized, and every tool call returns "Root CDP client not initialized".

## Rule: browser-use 0.13.1 config.json must have all three sections
`load_and_migrate_config()` only treats config as valid (DB-style) when ALL THREE top-level keys exist: `browser_profile`, `llm`, AND `agent`, AND each `browser_profile` value has an `'id'` field. If any section is missing it discards the file and regenerates fresh defaults — `cdp_url` is lost.

**Why:** The migration check at config.py line 329 is: `all(key in data for key in ['browser_profile', 'llm', 'agent'])`. One missing key → "old format" → fresh defaults → no cdp_url.

## Chrome binary location in Replit
Binary is at `{workspace_root}/.cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell` (workspace dir, NOT `~/.cache/ms-playwright`).

## How to apply
1. `asyncio.create_subprocess_exec(chrome_binary, f'--remote-debugging-port={port}', ...)`
2. Poll `http://localhost:{port}/json/version` with aiohttp until 200.
3. `playwright.chromium.connect_over_cdp(cdp_url)` — works fine over TCP.
4. Write config.json with all three sections, UUID keys, and `"id"` in each entry.
5. Set `BROWSER_USE_CONFIG_DIR` before starting the MCP server.
