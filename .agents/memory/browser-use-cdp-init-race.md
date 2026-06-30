---
name: browser-use CDP init race fix
description: How _cdp_client_root=None and broken sessions are fixed in the browser-use MCP bridge
---

## The rule
Any time BrowserSession.start() can fail before _cdp_client_root is set,
the MCP server ends up with a permanently broken browser_session.
The fix is a two-part monkey-patch on BrowserUseServer._init_browser_session.

## Why
browser-use 0.13.1 (_init_browser_session, mcp/server.py lines 608-609):
  self.browser_session = BrowserSession(...)  # set BEFORE start()
  await self.browser_session.start()          # may raise
If start() raises, browser_session holds a BrowserSession where
_cdp_client_root=None. Subsequent tool calls see `if self.browser_session: return`
— init is skipped forever, all tools assert _cdp_client_root → crash.

start() call chain:
  start() → dispatch BrowserStartEvent → on_BrowserStartEvent() →
  asyncio.wait_for(connect(cdp_url=...), timeout=15s) →
  connect() → GET http://localhost:PORT/json/version  (connection refused if Chrome cold)
  → connect() except: _cdp_client_root=None, raise RuntimeError
  → on_BrowserStartEvent except: dispatch BrowserErrorEvent, raise
  → start() event_result(raise_if_any=True) raises
  → _init_browser_session line 609 raises, but line 608 already ran.

## How to apply
In browser_use_bridge.py, _patch_mcp_server_session_retry(chrome_ready):

Part 1 — wait for Chrome:
  Patched _init_browser_session awaits chrome_ready asyncio.Event (set by
  _start_chrome_background when /json/version returns 200) before calling
  original(). This ensures connect() never sees "connection refused".

Part 2 — reset on failure:
  Wrap original() in try/except; on any exception reset self.browser_session=None
  so the next tool call creates a fresh BrowserSession and retries.

chrome_ready.set() is called unconditionally (even on 90s timeout) so the
tool call is never blocked forever.

## Class name
The MCP server class is BrowserUseServer (not BrowserMCPServer).
Import: from browser_use.mcp.server import BrowserUseServer
