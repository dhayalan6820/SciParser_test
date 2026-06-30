"""
browser_use_bridge.py
─────────────────────
Launches Chromium via Playwright (proven to work in Replit), then points
browser-use's MCP server at the SAME browser via CDP URL.

Architecture
  1. async_playwright launches Chrome with --remote-debugging-port=PORT
  2. We write a browser-use config.json with  cdp_url = http://localhost:PORT
  3. browser-use MCP server reads that config and connects — no new browser launched
  4. Playwright tools (in ATAG / scripts) and browser-use MCP tools share one Chrome
"""

import asyncio
import inspect
import json
import os
import socket
import sys
import tempfile


def _find_free_port() -> int:
    """Ask the OS for an unused TCP port (fallback when env var is not set)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


# ── Sandbox args required for headless Chrome in Replit / sandboxed Linux ─────
_SANDBOX_ARGS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-setuid-sandbox",
    "--remote-allow-origins=*",
]


def _write_browser_use_config(config_dir: str, cdp_url: str, headless: bool) -> None:
    """Write a minimal browser-use config.json that points MCP server at cdp_url."""
    os.makedirs(config_dir, exist_ok=True)
    config = {
        "browser_profile": {
            "default": {
                "default": True,
                "cdp_url": cdp_url,
                "headless": headless,
                "disable_security": True,
                "keep_alive": True,
            }
        }
    }
    config_path = os.path.join(config_dir, "config.json")
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    print(f"Bridge: wrote browser-use config → {config_path}", file=sys.stderr)


async def run_bridge() -> None:
    from playwright.async_api import async_playwright
    from browser_use.mcp.server import main as mcp_main

    # ── Read env ────────────────────────────────────────────────────────────────
    port_env = os.getenv("BROWSER_USE_CDP_PORT")
    port = int(port_env) if port_env and port_env not in ("", "0") else _find_free_port()
    headless = os.getenv("BROWSER_USE_HEADLESS", "true").lower() != "false"
    user_data_dir = os.getenv("BROWSER_USER_DATA_DIR")

    # Isolated config dir per session so concurrent sessions don't collide
    config_dir = os.path.join(
        tempfile.gettempdir(), f"browser_use_cfg_{port}"
    )

    print(
        f"Bridge: port={port}  headless={headless}  user_data_dir={user_data_dir}",
        file=sys.stderr,
    )

    # ── Step 1: Launch Chrome via Playwright ────────────────────────────────────
    pw = await async_playwright().start()
    browser = None
    context = None

    try:
        launch_args = _SANDBOX_ARGS + [f"--remote-debugging-port={port}"]

        if user_data_dir:
            os.makedirs(user_data_dir, exist_ok=True)
            # launch_persistent_context returns a BrowserContext directly
            context = await pw.chromium.launch_persistent_context(
                user_data_dir,
                headless=headless,
                args=launch_args,
            )
        else:
            browser = await pw.chromium.launch(
                headless=headless,
                args=launch_args,
            )

        cdp_url = f"http://localhost:{port}"
        print(f"Bridge: Playwright launched Chrome at {cdp_url}", file=sys.stderr)

        # Expose to any other code that checks these env vars
        os.environ["BROWSER_CDP_URL"] = cdp_url
        os.environ["MCP_BROWSER_CDP_URL"] = cdp_url

    except Exception as exc:
        print(f"Bridge: Chrome launch failed — {exc}", file=sys.stderr)
        # Attempt cleanup and exit — MCP server can't work without a browser
        try:
            await pw.stop()
        except Exception:
            pass
        return

    # ── Step 2: Write browser-use config that points MCP at the same Chrome ────
    _write_browser_use_config(config_dir, cdp_url, headless)
    os.environ["BROWSER_USE_CONFIG_DIR"] = config_dir

    # ── Step 3: Start the browser-use MCP server ────────────────────────────────
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
        # ── Cleanup ──────────────────────────────────────────────────────────────
        if context:
            try:
                await context.close()
            except Exception:
                pass
        if browser:
            try:
                await browser.close()
            except Exception:
                pass
        try:
            await pw.stop()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(run_bridge())
