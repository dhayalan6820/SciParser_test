---
title: Connect user's local browser via CDP
---
# Connect User's Local Browser via CDP

## What & Why
The #1 cause of WAF blocks (Verizon, Frontier, AT&T, Cloudflare) on Replit is the datacenter IP address — not the browser fingerprint. The user's local Chrome browser already has a residential IP, real cookies, human browsing history, and saved sessions. Connecting to it directly via Chrome DevTools Protocol (CDP) bypasses all IP-based blocking completely and for free.

The user launches Chrome with `--remote-debugging-port=9222` (or clicks a helper script), and the Replit backend connects to it via CDP. The agent then controls the user's real Chrome instead of a headless server-side browser.

## Done looks like
- A "Connect Your Browser" button in the chat UI toolbar
- Clicking it shows a one-line command the user copies and runs in their terminal: `google-chrome --remote-debugging-port=9222` (with OS-specific variants for Mac/Windows)
- A "Test Connection" call from the backend checks `http://localhost:9222/json/version` via a WebSocket tunnel or user-provided CDP URL
- When connected, the browser engine switches to CDP mode — all automation runs in the user's real Chrome
- A green indicator in the toolbar shows "Browser Connected" vs "Cloud Browser"
- If the user closes their browser or the connection drops, the system falls back to the cloud browser automatically

## Out of scope
- Automatic Chrome launcher or native app installer
- Chrome extension approach (separate task if needed)
- Sharing the connected browser across multiple users

## Steps
1. **Backend CDP connection endpoint** — Add `POST /sciparser/v1/browser/connect-cdp` that accepts a `cdp_url` (e.g. `http://localhost:9222`), verifies the connection is reachable, and stores the URL in the user's session. Add `DELETE /sciparser/v1/browser/connect-cdp` to disconnect. Add `GET /sciparser/v1/browser/cdp-status` to check current connection state.
2. **Bridge CDP mode** — In `browser_use_bridge.py`, add a `cdp` engine path alongside the existing `chrome` and `camoufox` paths. When `BROWSER_ENGINE=cdp` (or when cdp_url is set in the session), connect Playwright to the remote CDP endpoint via `browser = await playwright.chromium.connect_over_cdp(cdp_url)` instead of launching a new browser.
3. **Session manager stores CDP URL** — In `brain.py` / `session_manager`, read the user's CDP URL from their session when initialising `MCPToolManager`. Pass it through to the bridge's `run_bridge()` call as an env var or argument.
4. **Frontend Connect button** — Add a "Connect Browser" button in the chat toolbar. Clicking it opens a small modal with: the command to run, an input for the CDP URL (default `http://localhost:9222`), and a "Connect" button that calls the backend endpoint. Show a green dot + "Your Browser" label when connected, grey dot + "Cloud Browser" when not.

## Relevant files
- `Backend/src/agents/browser_use_bridge.py:1296-1430`
- `Backend/src/services/brain.py:1276-1290`
- `Backend/src/main.py:1-60`
- `Frontend/src/components/ui/chat_page.tsx`
- `Frontend/src/api.ts`