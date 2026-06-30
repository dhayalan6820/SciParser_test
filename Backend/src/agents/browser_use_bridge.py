"""
browser_use_bridge.py
─────────────────────
We launch Chrome ourselves (plain asyncio subprocess, zero Playwright), wait
for its CDP port to open, then hand the CDP URL to browser-use via
browser_profile.cdp_url.  When cdp_url is pre-set, browser-use's
on_BrowserStartEvent skips LocalBrowserWatchdog entirely and calls
connect(cdp_url=...) — so browser-use owns all DOM / screenshot / action
work and we keep full control over the port used by our screenshot streamer.

Root-cause notes (browser-use 0.13.1)
──────────────────────────────────────
start() flow:
  BrowserSession.start()
    → dispatch BrowserStartEvent
    → on_BrowserStartEvent()
        → if cdp_url already set: skip Chrome launch
        → asyncio.wait_for(self.connect(cdp_url=...), timeout=15s)
          → connect(): GET http://localhost:PORT/json/version  ← fails if Chrome cold
            → except: self._cdp_client_root = None; raise
        → on timeout: self._cdp_client_root = None; raise
    → exception re-raised
  back in _init_browser_session():
    line 608: self.browser_session = BrowserSession(...)   ← ALREADY SET
    line 609: await self.browser_session.start()           ← raises
  Result: browser_session is non-None but _cdp_client_root is None.
  Every subsequent tool call: `if self.browser_session: return` → init skipped
  → tools assert _cdp_client_root → "Root CDP client not initialized"

Two-part fix applied here:
  1. _patch_mcp_server_session_retry():
       Wraps _init_browser_session so any exception resets browser_session=None,
       enabling a clean retry on the next tool call.
  2. chrome_ready_event (asyncio.Event):
       _init_browser_session waits for Chrome to be confirmed ready BEFORE
       calling BrowserSession.start(), so the first attempt succeeds
       instead of failing with "connection refused".
"""

import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile


CHROME_BINARY = (
    "/home/runner/workspace/.cache/ms-playwright"
    "/chromium-1228/chrome-linux64/chrome"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


async def _wait_for_cdp(port: int, timeout_secs: int = 90) -> bool:
    """Poll http://localhost:PORT/json/version until Chrome is ready."""
    import aiohttp

    url = f"http://localhost:{port}/json/version"
    for _ in range(timeout_secs):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=1)
                ) as resp:
                    if resp.status == 200:
                        return True
        except Exception:
            pass
        await asyncio.sleep(1)
    return False


# ---------------------------------------------------------------------------
# Chrome subprocess launch
# ---------------------------------------------------------------------------


async def _launch_chrome(
    port: int,
    user_data_dir: str,
    headless: bool,
) -> asyncio.subprocess.Process:
    """
    Launch Chrome as a plain subprocess (no Playwright).
    Returns the Process handle (caller is responsible for cleanup).
    """
    args = [
        CHROME_BINARY,
        # CDP port — the single source of truth for both our screenshotter
        # and browser-use's connect()
        f"--remote-debugging-port={port}",
        "--remote-allow-origins=*",
        # Required in Replit / Docker environment
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--disable-setuid-sandbox",
        "--no-first-run",
        "--no-default-browser-check",
        # Bypass Replit's internal proxy
        "--no-proxy-server",
        # Viewport for screenshots
        "--window-size=1280,800",
        # Stealth — removes navigator.webdriver fingerprint
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        "--disable-notifications",
        "--disable-popup-blocking",
        "--disable-default-apps",
        "--mute-audio",
        "--lang=en-US,en",
        # Realistic UA to bypass Azure / Cloudflare WAF bot detection
        (
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        # Profile directory
        f"--user-data-dir={user_data_dir}",
    ]

    if headless:
        args.append("--headless=new")

    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    print(
        f"Bridge: Chrome launched — pid={proc.pid}  port={port}",
        file=sys.stderr,
    )
    return proc


# ---------------------------------------------------------------------------
# browser-use config writer
# ---------------------------------------------------------------------------


def _write_browser_use_config(
    config_dir: str,
    cdp_url: str,
    user_data_dir: str,
) -> None:
    """
    Write a browser-use config.json.

    cdp_url is set so browser-use skips LocalBrowserWatchdog entirely and
    connects directly — no launch timeout possible.
    """
    import uuid
    from datetime import datetime, timezone

    os.makedirs(config_dir, exist_ok=True)

    now_iso = datetime.now(timezone.utc).isoformat()
    profile_id = str(uuid.uuid4())
    llm_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())

    config = {
        "browser_profile": {
            profile_id: {
                "id": profile_id,
                "default": True,
                "created_at": now_iso,
                # Pre-set cdp_url → browser-use connects instead of launching
                "cdp_url": cdp_url,
                "is_local": False,
                "user_data_dir": user_data_dir,
                "headless": False,        # Chrome already running; ignored
                "disable_security": True,
                "keep_alive": True,
                "chromium_sandbox": False,
            }
        },
        "llm": {
            llm_id: {
                "id": llm_id,
                "default": True,
                "created_at": now_iso,
                "model": "gpt-4.1-mini",
                "api_key": os.getenv("OPENAI_API_KEY", "placeholder"),
            }
        },
        "agent": {
            agent_id: {
                "id": agent_id,
                "default": True,
                "created_at": now_iso,
            }
        },
    }

    config_path = os.path.join(config_dir, "config.json")
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    print(f"Bridge: wrote browser-use config → {config_path}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Monkey-patch: wait for Chrome + reset browser_session on failure
# ---------------------------------------------------------------------------


def _patch_mcp_server_session_retry(chrome_ready: asyncio.Event) -> None:
    """
    Two-part patch applied to BrowserUseServer._init_browser_session:

    Part 1 — wait for Chrome before attempting start():
        browser-use's connect() calls GET http://localhost:PORT/json/version.
        If Chrome is still cold-starting that call fails immediately
        (connection refused), start() raises, and the broken browser_session
        is stored (see Part 2).  We avoid this entirely by awaiting the
        chrome_ready Event (set by _start_chrome_background once /json/version
        returns 200) before calling the original _init_browser_session.

    Part 2 — reset browser_session on failure:
        _init_browser_session sets self.browser_session = BrowserSession(...)
        on line 608 BEFORE calling start() on line 609.  If start() raises,
        the broken session is stored; every subsequent tool call sees
        `if self.browser_session: return` as True — init is skipped, tools
        run against _cdp_client_root=None forever.
        We catch the exception and reset self.browser_session = None so the
        NEXT tool call gets a clean retry.
    """
    try:
        from browser_use.mcp.server import BrowserUseServer as BrowserMCPServer
    except ImportError:
        print(
            "Bridge: could not import BrowserUseServer — skipping patch",
            file=sys.stderr,
        )
        return

    original = BrowserMCPServer._init_browser_session

    async def _patched_init(self, *args, **kwargs):
        # Part 1: wait until Chrome is confirmed ready (up to 90s).
        # This runs only once — after that the Event stays set forever.
        if not chrome_ready.is_set():
            print(
                "Bridge [patch]: waiting for Chrome to be ready...",
                file=sys.stderr,
            )
            try:
                await asyncio.wait_for(chrome_ready.wait(), timeout=90.0)
                print(
                    "Bridge [patch]: Chrome is ready — proceeding with BrowserSession.start()",
                    file=sys.stderr,
                )
            except asyncio.TimeoutError:
                print(
                    "Bridge [patch]: timed out waiting for Chrome (90s) — attempting anyway",
                    file=sys.stderr,
                )

        # Part 2: reset browser_session on any start() failure.
        try:
            await original(self, *args, **kwargs)
        except Exception as exc:
            # Reset so the next tool call retries from scratch.
            self.browser_session = None
            print(
                f"Bridge [patch]: _init_browser_session failed ({exc!r}) — "
                "reset browser_session=None so next tool call retries",
                file=sys.stderr,
            )
            raise

    BrowserMCPServer._init_browser_session = _patched_init
    print(
        "Bridge: BrowserUseServer._init_browser_session patched "
        "(wait-for-Chrome + retry-on-failure)",
        file=sys.stderr,
    )


# ---------------------------------------------------------------------------
# Main bridge coroutine
# ---------------------------------------------------------------------------


async def run_bridge() -> None:
    import inspect
    from browser_use.mcp.server import main as mcp_main

    # ── Read env (set by MCPToolManager in the parent process) ──────────────
    port_env = os.getenv("BROWSER_USE_CDP_PORT")
    port = (
        int(port_env) if port_env and port_env not in ("", "0") else _find_free_port()
    )
    headless = os.getenv("BROWSER_USE_HEADLESS", "true").lower() != "false"
    user_data_dir = os.getenv(
        "BROWSER_USER_DATA_DIR",
        tempfile.mkdtemp(prefix="browser-use-user-data-dir-"),
    )
    os.makedirs(user_data_dir, exist_ok=True)

    cdp_url = f"http://localhost:{port}"
    config_dir = os.path.join(tempfile.gettempdir(), f"browser_use_cfg_{port}")

    print(
        f"Bridge: port={port}  headless={headless}  user_data_dir={user_data_dir}",
        file=sys.stderr,
    )

    # ── Write config BEFORE starting Chrome — cdp_url is already known ──────
    _write_browser_use_config(config_dir, cdp_url, user_data_dir)
    os.environ["BROWSER_USE_CONFIG_DIR"] = config_dir
    os.environ["BROWSER_CDP_URL"] = cdp_url
    os.environ["MCP_BROWSER_CDP_URL"] = cdp_url

    # ── Shared Event: set when Chrome is confirmed ready ─────────────────────
    # _start_chrome_background sets it; the patched _init_browser_session
    # awaits it before attempting BrowserSession.start().
    chrome_ready = asyncio.Event()

    # ── Launch Chrome in the background ──────────────────────────────────────
    # We must NOT block here — mcp_agent.py has a 60 s timeout waiting for
    # the MCP "initialize" handshake.  Chrome cold-start can take up to 60 s
    # on Replit, so waiting synchronously would exhaust the budget before the
    # MCP server even starts.  Chrome starts concurrently; the patched
    # _init_browser_session awaits chrome_ready before calling start().
    chrome_proc: asyncio.subprocess.Process | None = None

    async def _start_chrome_background() -> None:
        nonlocal chrome_proc
        print("Bridge: launching Chrome in background...", file=sys.stderr)
        chrome_proc = await _launch_chrome(port, user_data_dir, headless)
        ready = await _wait_for_cdp(port, timeout_secs=90)
        if ready:
            print(f"Bridge: Chrome ready at {cdp_url}", file=sys.stderr)
            chrome_ready.set()          # ← unblocks patched _init_browser_session
        else:
            print(f"Bridge: Chrome CDP not ready after 90s", file=sys.stderr)
            chrome_ready.set()          # ← unblock anyway; start() will fail+retry

    asyncio.create_task(_start_chrome_background())

    # ── Patch BrowserUseServer._init_browser_session ─────────────────────────
    _patch_mcp_server_session_retry(chrome_ready)

    # ── Start browser-use MCP server immediately ─────────────────────────────
    try:
        print("Bridge: starting browser-use MCP server...", file=sys.stderr)
        if inspect.iscoroutinefunction(mcp_main):
            await mcp_main()
        else:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, mcp_main)
    except Exception as exc:
        print(f"Bridge: MCP server error — {exc}", file=sys.stderr)
    finally:
        print("Bridge: shutting down Chrome...", file=sys.stderr)
        if chrome_proc is not None:
            try:
                chrome_proc.terminate()
                await asyncio.wait_for(chrome_proc.wait(), timeout=5)
            except Exception:
                chrome_proc.kill()
        print("Bridge: cleanup complete", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(run_bridge())
