---
title: Residential proxy support for bot-blocked sites
---
# Residential Proxy Support for Bot-Blocked Sites

## What & Why
When users cannot or do not want to connect their local browser, a residential proxy is the next best way to bypass WAF blocks on sites like Frontier, Verizon, and AT&T. Datacenter IPs (which Replit uses) are blocked by most telecom and financial sites. Routing browser traffic through a residential proxy makes the request appear to come from a home ISP.

The implementation adds proxy configuration to the browser launch arguments in the bridge, and a settings UI for users to enter their proxy credentials.

## Done looks like
- Users can enter a proxy URL in settings (e.g. `http://user:pass@proxy.brightdata.com:22225`)
- The proxy is applied to all browser sessions for that user
- If no proxy is configured, the browser launches without one (current behaviour)
- Works with all major proxy providers: Brightdata, Oxylabs, Smartproxy, or any HTTP/HTTPS proxy
- Proxy credentials are stored as an encrypted secret, not in plain DB columns

## Out of scope
- Per-domain proxy routing (same proxy for all sites)
- SOCKS5 proxy support (HTTP proxy only for now)
- Free proxy lists (user must provide their own)

## Steps
1. **Store proxy URL as user secret** — Add a `proxy_url` field to the user session/settings. Store it encrypted (use the existing secrets pattern). Add `POST /sciparser/v1/settings/proxy` and `DELETE /sciparser/v1/settings/proxy` endpoints.
2. **Pass proxy to browser launch** — In `browser_use_bridge.py`, read the proxy URL from env/args and pass it to Playwright's browser launch args: `proxy={"server": proxy_url}` for both Chromium and Camoufox paths. Also pass proxy to the MCP tool manager init.
3. **Settings UI** — Add a "Proxy" section in the app settings panel with a masked input for the proxy URL, a "Test Proxy" button that hits a known public IP-check URL and returns the exit IP, and a clear/remove option.
4. **Proxy indicator** — Show a small shield icon in the toolbar when a proxy is active, similar to the CDP connection indicator from the "Connect Your Browser" task.

## Relevant files
- `Backend/src/agents/browser_use_bridge.py:1296-1430`
- `Backend/src/services/brain.py:1276-1290`
- `Backend/src/main.py:1-60`
- `Frontend/src/components/ui/chat_page.tsx`
- `Frontend/src/api.ts`