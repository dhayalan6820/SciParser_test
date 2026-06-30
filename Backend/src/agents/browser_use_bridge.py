"""
browser_use_bridge.py
─────────────────────
Launches Chrome directly via subprocess so the CDP endpoint is TCP-accessible,
then lets browser-use's MCP server connect to that same Chrome instance.

Architecture
  1. Find the best available Chrome binary (full Chromium preferred over headless-shell)
  2. Start it via asyncio.create_subprocess_exec with --remote-debugging-port=PORT
  3. Poll http://localhost:PORT/json/version until CDP is ready (HTTP, not pipe)
  4. Connect Playwright to the running Chrome via connect_over_cdp()
  5. Write a browser-use config.json pointing cdp_url at the running Chrome
  6. Start the browser-use MCP server — it connects to existing Chrome, never launches its own

Anti-bot strategy (two-stage fallback)
  Option 1 (default): Full Chromium with --headless=new + stealth flags.
    --headless=new renders identically to a real browser (same GPU pipeline, JS
    fingerprint, navigator properties) and is much harder to detect than the old
    headless-shell.  --disable-blink-features=AutomationControlled removes the
    navigator.webdriver flag that most bot-detection services check.
  Option 2 (Xvfb fallback): If Option 1 fails (CDP never becomes ready) AND the
    Xvfb binary is available on the system, restart Chrome headed (no --headless)
    with a virtual X11 framebuffer so it runs completely invisibly.  Screenshots
    still work identically via CDP because Playwright reads the framebuffer.
    Set BROWSER_USE_XVFB=true to force Option 2 without waiting for Option 1 to fail.

WHY subprocess instead of playwright.launch():
  playwright.launch() uses an internal pipe (--remote-debugging-pipe), so even when
  --remote-debugging-port is passed in args the port is often not TCP-accessible.
  Using create_subprocess_exec guarantees Chrome listens on the TCP port.
"""

import asyncio
import glob
import json
import os
import shutil
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


def _playwright_search_roots() -> list:
    workspace_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..")
    )
    home_pw = os.path.expanduser("~/.cache/ms-playwright")
    workspace_pw = os.path.join(workspace_root, ".cache", "ms-playwright")
    pw_env = os.getenv("PLAYWRIGHT_BROWSERS_PATH", "")
    return [r for r in [pw_env, workspace_pw, home_pw] if r]


def _find_full_chrome_binary() -> str | None:
    """
    Locate the FULL Chromium binary (not headless-shell).
    Full Chromium supports --headless=new which is near-invisible to bot detection.
    Returns None if not found.
    """
    patterns = [
        os.path.join("chromium-*", "chrome-linux64", "chrome"),
        os.path.join("chromium-*", "chrome-linux", "chrome"),
    ]
    for root in _playwright_search_roots():
        for pat in patterns:
            matches = glob.glob(os.path.join(root, pat))
            if matches:
                return matches[0]
    return None


def _find_headless_shell_binary() -> str | None:
    """Locate the chrome-headless-shell binary installed by Playwright."""
    patterns = [
        os.path.join(
            "chromium_headless_shell-*",
            "chrome-headless-shell-linux64",
            "chrome-headless-shell",
        ),
        os.path.join("chromium_headless_shell-*", "chrome-headless-shell"),
    ]
    for root in _playwright_search_roots():
        for pat in patterns:
            matches = glob.glob(os.path.join(root, pat))
            if matches:
                return matches[0]
    return None


def _find_any_chrome_binary() -> str:
    """
    Return the best available Chrome binary.
    Preference order: full Chromium → headless-shell.
    Raises RuntimeError if neither is found.
    """
    binary = _find_full_chrome_binary() or _find_headless_shell_binary()
    if binary:
        return binary
    raise RuntimeError(
        "No Chrome binary found. Run: python -m playwright install chromium"
    )


def _is_full_chromium(binary_path: str) -> bool:
    """True when the binary is full Chromium (not headless-shell)."""
    return "headless-shell" not in os.path.basename(binary_path)


def _find_xvfb() -> str | None:
    """Return path to Xvfb binary if available, else None."""
    return shutil.which("Xvfb")


# ---------------------------------------------------------------------------
# Chrome flags
# ---------------------------------------------------------------------------

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

# Option 1 stealth flags — remove bot-detection fingerprints
_STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-infobars",
    "--disable-notifications",
    "--disable-popup-blocking",
    "--disable-default-apps",
    "--mute-audio",
    "--lang=en-US,en",
]


# ---------------------------------------------------------------------------
# CDP helpers
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# browser-use config
# ---------------------------------------------------------------------------


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
# Chrome launch helpers
# ---------------------------------------------------------------------------


async def _launch_chrome(
    binary: str,
    port: int,
    user_data_dir: str,
    headless: bool,
    display: str | None = None,
) -> "asyncio.subprocess.Process":
    """
    Build the Chrome command and start it.

    headless=True  + full Chromium   → --headless=new  (Option 1, stealth)
    headless=False + full Chromium   → no --headless   (Option 2, Xvfb virtual display)
    headless=True  + headless-shell  → --headless      (legacy fallback)
    """
    cmd = [
        binary,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
        *_SANDBOX_ARGS,
        *_STEALTH_ARGS,
    ]

    if headless:
        if _is_full_chromium(binary):
            cmd.append("--headless=new")
        else:
            cmd.append("--headless")
    else:
        # Headed mode — requires a display (real or virtual)
        cmd.append("--start-maximized")
        cmd.append("--window-size=1280,800")

    env = os.environ.copy()
    if display:
        env["DISPLAY"] = display

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )
    return proc


async def _start_xvfb(display_num: int = 99) -> "asyncio.subprocess.Process | None":
    """
    Start a virtual X11 framebuffer on :{display_num}.
    Returns the process on success, None if Xvfb is not available.
    """
    xvfb = _find_xvfb()
    if not xvfb:
        return None
    try:
        proc = await asyncio.create_subprocess_exec(
            xvfb,
            f":{display_num}",
            "-screen", "0", "1280x800x24",
            "-ac",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        await asyncio.sleep(1)  # give Xvfb a moment to initialise
        return proc
    except Exception as exc:
        print(f"Bridge: Xvfb start failed — {exc}", file=sys.stderr)
        return None


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
    force_xvfb = os.getenv("BROWSER_USE_XVFB", "false").lower() == "true"
    user_data_dir = os.getenv("BROWSER_USER_DATA_DIR") or tempfile.mkdtemp(
        prefix="chrome_cdp_"
    )
    os.makedirs(user_data_dir, exist_ok=True)

    config_dir = os.path.join(tempfile.gettempdir(), f"browser_use_cfg_{port}")
    cdp_url = f"http://localhost:{port}"

    # ── Step 1: Find Chrome binary ───────────────────────────────────────────────
    try:
        chrome_binary = _find_any_chrome_binary()
    except RuntimeError as exc:
        print(f"Bridge: {exc}", file=sys.stderr)
        return

    is_full = _is_full_chromium(chrome_binary)
    print(
        f"Bridge: port={port}  headless={headless}  full_chromium={is_full}  "
        f"force_xvfb={force_xvfb}  user_data_dir={user_data_dir}",
        file=sys.stderr,
    )
    print(f"Bridge: Chrome binary → {chrome_binary}", file=sys.stderr)

    # ── Step 2 / Option selection ────────────────────────────────────────────────
    # Option 1: Full Chromium + --headless=new + stealth flags (default)
    # Option 2: Full Chromium + Xvfb virtual display (headed) → better for
    #           sites that detect headless mode even with stealth flags.
    #           Triggered automatically if Option 1 CDP never becomes ready,
    #           or forced via BROWSER_USE_XVFB=true.

    chrome_process = None
    xvfb_process = None
    effective_headless = headless  # passed to browser-use config

    if force_xvfb and headless:
        # BROWSER_USE_XVFB=true overrides headless — use Option 2 directly
        print("Bridge: BROWSER_USE_XVFB=true — skipping to Option 2", file=sys.stderr)
        headless = False

    # ── Option 1: Start Chrome (headless or headless=new) ────────────────────────
    if headless or not _find_xvfb():
        print(f"Bridge: [Option 1] launching Chrome with stealth flags", file=sys.stderr)
        chrome_process = await _launch_chrome(
            chrome_binary, port, user_data_dir, headless=True
        )
        print(
            f"Bridge: Chrome pid={chrome_process.pid} started, waiting for CDP...",
            file=sys.stderr,
        )
        cdp_ready = await _wait_for_cdp(port, timeout_secs=25)

        if not cdp_ready:
            print(
                f"Bridge: [Option 1] Chrome failed to expose CDP — trying Option 2 (Xvfb headed mode)",
                file=sys.stderr,
            )
            chrome_process.terminate()
            chrome_process = None
            headless = False  # fall through to Option 2

    # ── Option 2: Xvfb + headed Chrome ───────────────────────────────────────────
    if not headless and chrome_process is None:
        xvfb_bin = _find_xvfb()
        if xvfb_bin:
            display_num = _find_free_port() % 200 + 10  # pick a free display number
            print(
                f"Bridge: [Option 2] starting Xvfb on :{display_num}",
                file=sys.stderr,
            )
            xvfb_process = await _start_xvfb(display_num)
            if xvfb_process:
                display = f":{display_num}"
                chrome_process = await _launch_chrome(
                    chrome_binary, port, user_data_dir,
                    headless=False, display=display,
                )
                print(
                    f"Bridge: [Option 2] Chrome pid={chrome_process.pid} "
                    f"headed DISPLAY={display}, waiting for CDP...",
                    file=sys.stderr,
                )
                cdp_ready = await _wait_for_cdp(port, timeout_secs=25)
                if not cdp_ready:
                    print(
                        "Bridge: [Option 2] Xvfb Chrome also failed to expose CDP — aborting",
                        file=sys.stderr,
                    )
                    chrome_process.terminate()
                    xvfb_process.terminate()
                    return
                effective_headless = False
            else:
                print("Bridge: Xvfb unavailable, aborting (no display)", file=sys.stderr)
                return
        else:
            # Xvfb not installed — fall back to Option 1 anyway
            print(
                "Bridge: Xvfb binary not found — retrying Option 1 (headless=new)",
                file=sys.stderr,
            )
            chrome_process = await _launch_chrome(
                chrome_binary, port, user_data_dir, headless=True
            )
            cdp_ready = await _wait_for_cdp(port, timeout_secs=25)
            if not cdp_ready:
                print("Bridge: Chrome failed to start — aborting", file=sys.stderr)
                chrome_process.terminate()
                return
            effective_headless = True

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

    # ── Step 5: Write browser-use config pointing at cdp_url ────────────────────
    _write_browser_use_config(config_dir, cdp_url, effective_headless)
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
        if xvfb_process:
            try:
                xvfb_process.terminate()
            except Exception:
                pass
        print("Bridge: cleanup complete", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(run_bridge())
