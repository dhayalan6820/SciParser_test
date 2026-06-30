"""
browser_use_bridge.py
─────────────────────
Launches Chrome directly via subprocess so the CDP endpoint is TCP-accessible,
then lets browser-use's MCP server connect to that same Chrome instance.

Architecture
  1. Find the chrome-headless-shell binary installed by Playwright
  2. Start it via asyncio.create_subprocess_exec with --remote-debugging-port=PORT
  3. Poll http://localhost:PORT/json/version until CDP is ready (HTTP, not pipe)
  4. Connect Playwright to the running Chrome via connect_over_cdp()
  5. Write a browser-use config.json pointing cdp_url at the running Chrome
  6. Start the browser-use MCP server — it connects to existing Chrome, never launches its own

WHY subprocess instead of playwright.launch():
  playwright.launch() uses an internal pipe (--remote-debugging-pipe), so even when
  --remote-debugging-port is passed in args the port is often not TCP-accessible.
  Using create_subprocess_exec guarantees Chrome listens on the TCP port.
"""

import asyncio
import glob
import json
import os
import socket
import subprocess
import sys
import tempfile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _find_chrome_binary() -> str:
    """Locate the chrome-headless-shell binary installed by Playwright."""
    # Playwright may install browsers into the workspace dir (Replit) or the user home dir
    workspace_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..")
    )
    home_pw = os.path.expanduser("~/.cache/ms-playwright")
    workspace_pw = os.path.join(workspace_root, ".cache", "ms-playwright")
    pw_env = os.getenv("PLAYWRIGHT_BROWSERS_PATH", "")

    search_roots = [r for r in [pw_env, workspace_pw, home_pw] if r]

    sub_patterns = [
        os.path.join(
            "chromium_headless_shell-*",
            "chrome-headless-shell-linux64",
            "chrome-headless-shell",
        ),
        os.path.join("chromium-*", "chrome-linux", "chrome"),
        os.path.join("chromium_headless_shell-*", "chrome-headless-shell"),
    ]

    for root in search_roots:
        for sub in sub_patterns:
            matches = glob.glob(os.path.join(root, sub))
            if matches:
                return matches[0]

    searched = [os.path.join(r, s) for r in search_roots for s in sub_patterns]
    raise RuntimeError(
        "chrome-headless-shell binary not found. "
        f"Run: python -m playwright install chromium.  Searched: {searched}"
    )


_SANDBOX_ARGS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-setuid-sandbox",
    "--remote-allow-origins=*",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-extensions",
]


async def _wait_for_cdp(port: int, timeout_secs: int = 25) -> bool:
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


def _write_browser_use_config(config_dir: str, cdp_url: str, headless: bool) -> None:
    """
    Write a browser-use config.json in DB-style format pointing the MCP server at cdp_url.

    browser-use 0.13.1 load_and_migrate_config() treats the file as valid ONLY when:
      1. ALL THREE top-level keys exist: browser_profile, llm, agent
      2. Each value in browser_profile has an 'id' field

    If either condition fails it discards the file and regenerates fresh defaults,
    which means our cdp_url is lost and MCP launches its own browser instead.
    """
    import uuid

    os.makedirs(config_dir, exist_ok=True)

    from datetime import datetime, timezone

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
                "cdp_url": cdp_url,
                "headless": headless,
                "disable_security": True,
                "keep_alive": True,
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
    print(
        f"Bridge: wrote browser-use config (DB-style) → {config_path}", file=sys.stderr
    )


# ---------------------------------------------------------------------------
# Main bridge coroutine
# ---------------------------------------------------------------------------


async def run_bridge() -> None:
    import inspect
    from browser_use.mcp.server import main as mcp_main

    # ── Read env ────────────────────────────────────────────────────────────────
    port_env = os.getenv("BROWSER_USE_CDP_PORT")
    port = (
        int(port_env) if port_env and port_env not in ("", "0") else _find_free_port()
    )
    headless = os.getenv("BROWSER_USE_HEADLESS", "true").lower() != "false"
    user_data_dir = os.getenv("BROWSER_USER_DATA_DIR") or tempfile.mkdtemp(
        prefix="chrome_cdp_"
    )
    os.makedirs(user_data_dir, exist_ok=True)

    config_dir = os.path.join(tempfile.gettempdir(), f"browser_use_cfg_{port}")
    cdp_url = f"http://localhost:{port}"

    print(
        f"Bridge: port={port}  headless={headless}  user_data_dir={user_data_dir}",
        file=sys.stderr,
    )

    # ── Step 1: Find Chrome binary ───────────────────────────────────────────────
    try:
        chrome_binary = _find_chrome_binary()
    except RuntimeError as exc:
        print(f"Bridge: {exc}", file=sys.stderr)
        return

    print(f"Bridge: Chrome binary → {chrome_binary}", file=sys.stderr)

    # ── Step 2: Start Chrome directly via subprocess ─────────────────────────────
    cmd = [
        chrome_binary,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
        *_SANDBOX_ARGS,
    ]
    if headless:
        cmd.append("--headless")

    chrome_process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(
        f"Bridge: Chrome pid={chrome_process.pid} started, waiting for CDP...",
        file=sys.stderr,
    )

    # ── Step 3: Wait for CDP TCP port to be ready ────────────────────────────────
    cdp_ready = await _wait_for_cdp(port, timeout_secs=25)
    if not cdp_ready:
        print(
            f"Bridge: Chrome failed to expose CDP on port {port} within 25 s",
            file=sys.stderr,
        )
        chrome_process.terminate()
        return

    print(f"Bridge: CDP ready at {cdp_url}", file=sys.stderr)
    os.environ["BROWSER_CDP_URL"] = cdp_url
    os.environ["MCP_BROWSER_CDP_URL"] = cdp_url

    # ── Step 4: Connect Playwright to the running Chrome via CDP ─────────────────
    pw = None
    pw_browser = None
    try:
        from playwright.async_api import async_playwright

        pw = await async_playwright().start()
        pw_browser = await pw.chromium.connect_over_cdp(cdp_url)

        # Ensure at least one page exists so browser-use has something to work with
        contexts = pw_browser.contexts
        if contexts and contexts[0].pages:
            page = contexts[0].pages[0]
        else:
            ctx = await pw_browser.new_context()
            page = await ctx.new_page()

        print(
            f"Bridge: Playwright connected via CDP, page url={page.url}",
            file=sys.stderr,
        )
    except Exception as exc:
        print(
            f"Bridge: Playwright CDP connect warning — {exc} (non-fatal)",
            file=sys.stderr,
        )
        # Non-fatal — browser-use will connect to Chrome directly via the cdp_url

    # ── Step 5: Write browser-use config pointing at cdp_url ────────────────────
    _write_browser_use_config(config_dir, cdp_url, headless)
    os.environ["BROWSER_USE_CONFIG_DIR"] = config_dir

    # ── Step 6: Start the browser-use MCP server ─────────────────────────────────
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
        # ── Cleanup ──────────────────────────────────────────────────────────────
        if pw_browser:
            try:
                await pw_browser.close()
            except Exception:
                pass
        if pw:
            try:
                await pw.stop()
            except Exception:
                pass
        if chrome_process:
            try:
                chrome_process.terminate()
                await asyncio.wait_for(chrome_process.wait(), timeout=5)
            except Exception:
                try:
                    chrome_process.kill()
                except Exception:
                    pass
        print("Bridge: cleanup complete", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(run_bridge())
