"""
browser_use_bridge.py
─────────────────────
browser-use manages Chrome entirely through its own Playwright integration.
We no longer launch Chrome ourselves or import Playwright directly.

Architecture (simplified):
  1. Pick a free CDP port
  2. Write a browser-use config with extra Chrome args including
     --remote-debugging-port=PORT so our CDP screenshot streamer
     can still connect to the same Chrome instance
  3. Start the browser-use MCP server — it launches and controls
     Chrome via its own internal Playwright when the first browser
     tool is called
  4. Our screenshot streamer polls localhost:PORT and captures frames
     as soon as Chrome becomes available (lazy — on first tool use)

Anti-bot:
  --disable-blink-features=AutomationControlled removes navigator.webdriver.
  A real-browser User-Agent string is injected so Azure/Cloudflare WAF
  cannot fingerprint headless Chrome by its UA.
"""

import asyncio
import json
import os
import socket
import sys
import tempfile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


async def _wait_for_cdp(port: int, timeout_secs: int = 30) -> bool:
    """Poll http://localhost:PORT/json/version until Chrome's CDP is ready."""
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
# browser-use config writer
# ---------------------------------------------------------------------------


def _write_browser_use_config(config_dir: str, cdp_port: int, headless: bool) -> None:
    """
    Write a browser-use config.json that tells the MCP server to launch
    Chrome itself with our custom args (sandbox flags + stealth + CDP port).

    Key fields:
      args          — extra CLI flags passed through browser-use → Playwright → Chrome
      headless      — headless mode toggle
      disable_security — disables CORS / CSP so the agent can interact freely
      keep_alive    — keep the browser open between tool calls
      chromium_sandbox — must be False in Docker/Replit environment
    """
    import uuid
    from datetime import datetime, timezone

    os.makedirs(config_dir, exist_ok=True)

    now_iso = datetime.now(timezone.utc).isoformat()
    profile_id = str(uuid.uuid4())
    llm_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())

    # Explicit path to the Chrome binary — Playwright inside browser-use must use
    # our local .cache/ms-playwright copy, NOT look in uvx's managed cache.
    chrome_binary = (
        "/home/runner/workspace/.cache/ms-playwright"
        "/chromium-1228/chrome-linux64/chrome"
    )

    extra_args = [
        # Expose CDP on a known TCP port so our screenshot streamer can connect
        f"--remote-debugging-port={cdp_port}",
        "--remote-allow-origins=*",
        # Sandbox / resource flags required in Replit container
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--disable-setuid-sandbox",
        "--no-first-run",
        "--no-default-browser-check",
        # Bypass Replit's internal proxy (prevents "couldn't reach this app" error)
        "--no-proxy-server",
        # Screenshot viewport
        "--window-size=1280,800",
        # Stealth — removes navigator.webdriver and automation fingerprints
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        "--disable-notifications",
        "--disable-popup-blocking",
        "--disable-default-apps",
        "--mute-audio",
        "--lang=en-US,en",
        # Realistic UA to pass Azure / Cloudflare WAF bot detection
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36",
    ]

    config = {
        "browser_profile": {
            profile_id: {
                "id": profile_id,
                "default": True,
                "created_at": now_iso,
                "headless": headless,
                "disable_security": True,
                "keep_alive": True,
                "chromium_sandbox": False,
                "executable_path": chrome_binary,
                "args": extra_args,
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

    config_dir = os.path.join(tempfile.gettempdir(), f"browser_use_cfg_{port}")
    cdp_url = f"http://localhost:{port}"

    print(
        f"Bridge: port={port}  headless={headless}  cdp_url={cdp_url}",
        file=sys.stderr,
    )

    # ── Write config — browser-use will launch Chrome itself ────────────────
    _write_browser_use_config(config_dir, port, headless)
    os.environ["BROWSER_USE_CONFIG_DIR"] = config_dir
    os.environ["BROWSER_CDP_URL"] = cdp_url
    os.environ["MCP_BROWSER_CDP_URL"] = cdp_url

    print(
        f"Bridge: CDP will be available at {cdp_url} once the first browser tool runs",
        file=sys.stderr,
    )

    # ── Start browser-use MCP server ─────────────────────────────────────────
    # browser-use launches and fully controls Chrome through its own Playwright
    # integration when the first browser tool is called (lazy init).
    try:
        print("Bridge: starting browser-use MCP server...", file=sys.stderr)
        if inspect.iscoroutinefunction(mcp_main):
            await mcp_main()
        else:
            loop = asyncio.get_running_loop()
            loop.run_in_executor(None, mcp_main)
    except Exception as exc:
        print(f"Bridge: MCP server error — {exc}", file=sys.stderr)
    finally:
        print("Bridge: cleanup complete", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(run_bridge())
