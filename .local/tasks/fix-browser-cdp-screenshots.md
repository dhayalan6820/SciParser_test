# Fix Live Browser Screenshot Stream

## What & Why
The browser bridge (`browser_use_bridge.py`) currently launches Chrome via `playwright.chromium.launch()` and writes a config.json pointing to a CDP URL — but browser-use's MCP server ignores the config and tries to find/launch its own Chrome via `uvx`, which fails ("Root CDP client not initialized"). No screenshots ever reach the frontend.

The fix follows the reference pattern from the user's attached code:
1. Start Chrome directly via `asyncio.create_subprocess_exec` with `--remote-debugging-port`
2. Wait for CDP to be ready by polling `http://localhost:PORT/json/version`
3. Connect Playwright to that same Chrome via `playwright.chromium.connect_over_cdp(cdp_url)`
4. Pass `BrowserSession(cdp_url=cdp_url)` to browser-use so it reuses the running Chrome instead of launching its own

## Done looks like
- Sending any browser-automation chat message opens the `BrowserPreview` panel in the frontend automatically
- The panel shows a live screenshot that updates roughly every 1.5 seconds as the agent browses
- Backend logs show `browser_get_state` returning base64 image data (no "Root CDP client not initialized" errors)
- The agent completes browser tasks successfully (navigates, reads page content, returns answers)

## Out of scope
- Changing the WebSocket frame broadcast path in `main.py` (already works)
- Frontend `BrowserPreview` UI changes (already works)
- Video recording or full-page scroll capture

## Steps
1. **Rewrite the Chrome launch in `browser_use_bridge.py`** — Replace the `playwright.chromium.launch()` call with a direct subprocess launch of the `chrome-headless-shell` binary (resolved from `PLAYWRIGHT_BROWSERS_PATH` env var or the hardcoded `~/.cache/ms-playwright` path) with `--remote-debugging-port=PORT --no-sandbox --disable-dev-shm-usage`. Poll `http://localhost:PORT/json/version` until CDP is ready (20 retries × 1 s), just like the reference code.

2. **Connect Playwright over CDP** — After Chrome is ready, call `playwright_instance.chromium.connect_over_cdp(cdp_url)` instead of launching a new browser. Get or create a page from the connected context. This gives us a `playwright_page` for screenshot capture.

3. **Start the browser-use MCP server with `cdp_url`** — Pass the CDP URL via the subprocess environment (`BROWSER_CDP_URL`, `MCP_BROWSER_CDP_URL`, or equivalent env var that browser-use reads) so its `BrowserSession` connects to the running Chrome rather than spawning a new one. Cross-reference the installed browser-use version's source to confirm the correct env var name.

4. **Capture and broadcast screenshots** — After the MCP session initializes, confirm `browser_get_state` returns base64 image data. Verify `brain.py`'s `_stream_browser_frames` successfully extracts and broadcasts frames over the WebSocket, and the frontend auto-opens `BrowserPreview`.

5. **Clean up on session end** — Ensure the Chrome subprocess is terminated and Playwright is disconnected cleanly when the MCP session closes (mirror the `finally` block in the reference code).

## Relevant files
- `Backend/src/agents/browser_use_bridge.py`
- `Backend/src/agents/mcp_agent.py:66-132`
- `Backend/src/services/brain.py`
- `Backend/start.sh`
- `attached_assets/Pasted-import-asyncio-import-os-import-subprocess-import-sys-i_1782809429853.txt`
