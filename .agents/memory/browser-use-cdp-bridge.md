---
name: browser-use CDP bridge fix
description: How to correctly connect browser-use MCP server to a locally-launched Chrome via CDP, bypassing LocalBrowserWatchdog
---

## Rule
`BrowserSession.__init__` line 375 forces `is_local=True` whenever the `cdp_url` **kwarg** is `None`, even if `browser_profile.cdp_url` is set. This triggers `LocalBrowserWatchdog` which searches for a local Chrome binary via `which`/PATH and fails with "No local browser path found" in the Replit sandbox.

**Fix:** Monkey-patch `BrowserUseServer._init_browser_session` to create `BrowserSession(cdp_url=<url>, is_local=False)` explicitly, bypassing all config-chain logic.

**Why:** The config.json approach (writing cdp_url to browser-use's config.json) populates `browser_profile.cdp_url` but does NOT pass `cdp_url` as a constructor kwarg, so line 375 still fires.

**How to apply:** See `Backend/src/agents/browser_use_bridge.py` → `_patch_mcp_server_session_retry()`. Apply the patch BEFORE `main()` runs. Also set `chrome_ready` asyncio.Event so the patch waits for Chrome CDP to be available before connecting.

## Verified working
Direct bridge test (2026-07-01): Chrome starts → BrowserSession connects → `browser_get_state` returns live state `{url: "about:blank", viewport: {width:1288, height:804}}`.

## E2E test gotcha
The e2e test suite reuses an existing chat session ID. Old failed executions are stored in DB and appear in chat history. A "No local browser path found" error seen in the test UI may be from a **previous** run, not the current execution. Always use a fresh session to verify.
