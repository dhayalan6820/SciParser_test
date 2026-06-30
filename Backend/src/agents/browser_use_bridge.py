"""
browser_use_bridge.py
─────────────────────
We launch Chrome ourselves (plain asyncio subprocess, zero Playwright), wait
for its CDP port to open, then hand the CDP URL to browser-use via
browser_profile.cdp_url.  When cdp_url is pre-set, browser-use's
on_BrowserStartEvent skips LocalBrowserWatchdog entirely and just calls
connect(cdp_url=...) — so browser-use owns all DOM / screenshot / action
work and we keep full control over the port used by our screenshot streamer.

Why not let browser-use launch Chrome (LocalBrowserWatchdog)?
  • LocalBrowserWatchdog always appends its OWN --remote-debugging-port flag,
    overriding ours.  Chrome listens on a random port; our screenshotter is
    polling the wrong port.
  • The 30-second BrowserStartEvent handler timeout races against the
    _wait_for_cdp_url(30s) inside LocalBrowserWatchdog.  A cold Chrome start
    on Replit hits this limit, leaving _cdp_client_root=None and corrupting
    the session (navigation works, browser_get_state / browser_screenshot
    fail).

What we do instead:
  1. Launch Chrome subprocess with all flags (including our CDP port).
  2. Poll http://localhost:PORT/json/version until Chrome is ready.
  3. Write browser-use config with cdp_url already set.
  4. Start browser-use MCP server — it connects via CDP immediately,
     no launch timeout possible.
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


async def _wait_for_cdp(port: int, timeout_secs: int = 60) -> bool:
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

    # ── Launch Chrome ────────────────────────────────────────────────────────
    print("Bridge: launching Chrome...", file=sys.stderr)
    chrome_proc = await _launch_chrome(port, user_data_dir, headless)

    # ── Wait for Chrome CDP to be ready (up to 60 s) ─────────────────────────
    print(f"Bridge: waiting for Chrome CDP at {cdp_url} ...", file=sys.stderr)
    ready = await _wait_for_cdp(port, timeout_secs=60)
    if not ready:
        print(
            f"Bridge: Chrome CDP not ready after 60s — aborting",
            file=sys.stderr,
        )
        chrome_proc.terminate()
        return

    print(f"Bridge: Chrome ready at {cdp_url}", file=sys.stderr)

    # ── Write browser-use config with cdp_url already set ───────────────────
    _write_browser_use_config(config_dir, cdp_url, user_data_dir)
    os.environ["BROWSER_USE_CONFIG_DIR"] = config_dir
    os.environ["BROWSER_CDP_URL"] = cdp_url
    os.environ["MCP_BROWSER_CDP_URL"] = cdp_url

    # ── Start browser-use MCP server ─────────────────────────────────────────
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
        try:
            chrome_proc.terminate()
            await asyncio.wait_for(chrome_proc.wait(), timeout=5)
        except Exception:
            chrome_proc.kill()
        print("Bridge: cleanup complete", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(run_bridge())
