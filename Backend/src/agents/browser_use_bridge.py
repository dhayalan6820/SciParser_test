"""
browser_use_bridge.py  (fixed)
──────────────────────────────
Fixes applied vs. the original:

FIX 1 — Chrome-ready polling uses httpx fallback when aiohttp absent
  Original _wait_for_cdp imported aiohttp at call-time with no fallback.
  If aiohttp is missing the coroutine raises immediately, chrome_ready.set()
  is called anyway (the "else" branch), and browser-use tries to connect to
  a Chrome that never opened its CDP port → "All connection attempts failed".
  Fix: try aiohttp first, fall back to httpx, then fall back to a raw socket
  probe — at least one of these is always available.

FIX 2 — Chrome stderr is drained to detect early crashes
  Chromium on some Replit tiers exits immediately (SIGILL / missing deps /
  wrong binary) and the original code swallows stderr entirely
  (stderr=DEVNULL). If Chrome exits before CDP is up the wait loop spins
  for 90 s and then unblocks chrome_ready anyway. Fix: use a PIPE for stderr
  and start a background drain task. We also poll proc.returncode inside the
  wait loop and abort fast when Chrome has already exited.

FIX 3 — cdp_url format aligned with browser-use expectation
  browser-use 0.13.x BrowserSession.connect(cdp_url=...) passes the value
  to playwright.chromium.connect_over_cdp(). Playwright expects the bare
  host:port form — NOT the http:// URL — when the argument is named
  cdp_url in some versions, but the http:// URL in others.
  We write cdp_url as "http://localhost:{port}" (correct for playwright
  connect_over_cdp) and also set the env vars for older shims.

FIX 4 — _start_chrome_background is awaited via a proper shield
  asyncio.create_task() schedules the coroutine but if the event loop is
  busy initialising the MCP server the task may not run before the first
  tool call hits the patch. Fix: the patch now awaits chrome_ready with a
  90 s timeout (unchanged) BUT also ensures the background task is created
  before mcp_main() is started, and the loop gets at least one iteration
  via asyncio.sleep(0) before the MCP server blocks.

FIX 5 — browser_session reset patch is made more robust
  If BrowserUseServer doesn't have _init_browser_session (API change in a
  newer browser-use release) the patch degrades gracefully instead of
  crashing with AttributeError.

FIX 6 — BROWSER_USE_CONFIG_DIR env var written before mcp_main starts
  In some environments mcp_main() reads config at import-time; we write
  the config and set the env var before any browser-use symbol is imported.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# Chrome binary — edit if your Playwright cache path differs
# ---------------------------------------------------------------------------

CHROME_BINARY = (
    "/home/runner/workspace/.cache/ms-playwright"
    "/chromium-1228/chrome-linux64/chrome"
)

# Fallbacks tried in order when the primary binary is missing
CHROME_BINARY_FALLBACKS = [
    "/usr/bin/google-chrome-stable",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium-browser",
    "/usr/bin/chromium",
    "/usr/local/bin/chromium",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _resolve_chrome_binary() -> str:
    """Return the first Chrome binary that actually exists on disk."""
    for candidate in [CHROME_BINARY] + CHROME_BINARY_FALLBACKS:
        if os.path.isfile(candidate):
            return candidate
    # Last resort — let the OS find it on PATH
    return "google-chrome"


async def _probe_port_raw(host: str, port: int) -> bool:
    """Pure asyncio TCP probe — no third-party lib needed."""
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=1.0
        )
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return True
    except Exception:
        return False


async def _wait_for_cdp(
    port: int,
    proc: asyncio.subprocess.Process,
    timeout_secs: int = 90,
) -> bool:
    """
    Poll http://localhost:{port}/json/version until Chrome is ready.

    Strategy (FIX 1 + FIX 2):
    - Try aiohttp first, httpx second, raw TCP socket third.
    - Inside every iteration check whether Chrome has already exited; if so
      bail immediately instead of wasting the full timeout.
    """
    url = f"http://localhost:{port}/json/version"

    for elapsed in range(timeout_secs):
        # FIX 2: detect Chrome crash early
        if proc.returncode is not None:
            print(
                f"Bridge: Chrome exited with code {proc.returncode} "
                f"after {elapsed}s — aborting CDP wait",
                file=sys.stderr,
            )
            return False

        # --- attempt 1: aiohttp ---
        try:
            import aiohttp  # type: ignore
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=1)
                ) as resp:
                    if resp.status == 200:
                        return True
            await asyncio.sleep(1)
            continue
        except ImportError:
            pass  # aiohttp not installed → try next
        except Exception:
            pass

        # --- attempt 2: httpx ---
        try:
            import httpx  # type: ignore
            async with httpx.AsyncClient(timeout=1.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return True
            await asyncio.sleep(1)
            continue
        except ImportError:
            pass  # httpx not installed → try raw socket
        except Exception:
            pass

        # --- attempt 3: raw TCP probe (FIX 1 ultimate fallback) ---
        if await _probe_port_raw("127.0.0.1", port):
            # Port is open — CDP is likely up even if we can't parse JSON
            return True

        await asyncio.sleep(1)

    return False


# ---------------------------------------------------------------------------
# Chrome stderr drain (FIX 2)
# ---------------------------------------------------------------------------


async def _drain_stderr(proc: asyncio.subprocess.Process) -> None:
    """Read Chrome stderr and echo to our stderr so crashes are visible."""
    if proc.stderr is None:
        return
    try:
        while True:
            line = await proc.stderr.readline()
            if not line:
                break
            decoded = line.decode(errors="replace").rstrip()
            if decoded:
                print(f"Chrome stderr: {decoded}", file=sys.stderr)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Chrome subprocess launch
# ---------------------------------------------------------------------------


async def _launch_chrome(
    port: int,
    user_data_dir: str,
    headless: bool,
) -> asyncio.subprocess.Process:
    binary = _resolve_chrome_binary()
    print(f"Bridge: using Chrome binary → {binary}", file=sys.stderr)

    args = [
        binary,
        f"--remote-debugging-port={port}",
        "--remote-allow-origins=*",
        "--no-sandbox",                         # required in Replit / Docker
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--disable-setuid-sandbox",
        "--no-first-run",
        "--no-default-browser-check",
        "--window-size=1280,800",
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        "--disable-notifications",
        "--disable-popup-blocking",
        "--disable-default-apps",
        "--mute-audio",
        "--lang=en-US,en",
        (
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        f"--user-data-dir={user_data_dir}",
    ]

    if headless:
        args.append("--headless=new")

    # FIX 2: capture stderr so we can detect crashes
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,   # ← was DEVNULL; now PIPE
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
    Write config.json for browser-use.

    cdp_url = "http://localhost:{port}" matches playwright's
    connect_over_cdp() expectation.
    """
    os.makedirs(config_dir, exist_ok=True)

    now_iso = datetime.now(timezone.utc).isoformat()
    profile_id = str(uuid.uuid4())
    llm_id     = str(uuid.uuid4())
    agent_id   = str(uuid.uuid4())

    config = {
        "browser_profile": {
            profile_id: {
                "id": profile_id,
                "default": True,
                "created_at": now_iso,
                "cdp_url": cdp_url,          # FIX 3: http://localhost:{port}
                "is_local": False,
                "user_data_dir": user_data_dir,
                "headless": False,
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
# Monkey-patch: wait for Chrome + reset browser_session on failure (FIX 5)
# ---------------------------------------------------------------------------


def _patch_mcp_server_session_retry(chrome_ready: asyncio.Event) -> None:
    """
    Wrap BrowserUseServer._init_browser_session with two guards:

    Guard 1 — Await chrome_ready before calling start().
    Guard 2 — Reset self.browser_session = None on any exception so the
               next tool call gets a clean retry instead of hitting a
               broken cached session forever.
    """
    try:
        from browser_use.mcp.server import BrowserUseServer  # type: ignore
    except ImportError:
        print(
            "Bridge: BrowserUseServer not importable — skipping patch",
            file=sys.stderr,
        )
        return

    # FIX 5: graceful degradation if the method was renamed
    if not hasattr(BrowserUseServer, "_init_browser_session"):
        print(
            "Bridge: _init_browser_session not found on BrowserUseServer "
            "(API may have changed) — skipping patch",
            file=sys.stderr,
        )
        return

    original = BrowserUseServer._init_browser_session

    async def _patched_init(self, allowed_domains: "list[str] | None" = None, **kwargs):
        # Guard 1 — wait for Chrome
        if not chrome_ready.is_set():
            print(
                "Bridge [patch]: waiting for Chrome ready event...",
                file=sys.stderr,
            )
            try:
                await asyncio.wait_for(chrome_ready.wait(), timeout=90.0)
                print(
                    "Bridge [patch]: Chrome ready — calling BrowserSession.start()",
                    file=sys.stderr,
                )
            except asyncio.TimeoutError:
                print(
                    "Bridge [patch]: 90 s timeout waiting for Chrome — proceeding anyway",
                    file=sys.stderr,
                )

        # Guard 2 — reset on failure
        try:
            await original(self, allowed_domains=allowed_domains, **kwargs)
        except Exception as exc:
            self.browser_session = None      # allow clean retry
            print(
                f"Bridge [patch]: _init_browser_session failed ({exc!r}) — "
                "reset browser_session=None for retry",
                file=sys.stderr,
            )
            raise

    BrowserUseServer._init_browser_session = _patched_init  # type: ignore[method-assign]
    print(
        "Bridge: patched _init_browser_session (chrome-wait + retry-on-fail)",
        file=sys.stderr,
    )


# ---------------------------------------------------------------------------
# Main bridge coroutine
# ---------------------------------------------------------------------------


async def run_bridge() -> None:
    import inspect

    # ── Read env ─────────────────────────────────────────────────────────────
    port_env = os.getenv("BROWSER_USE_CDP_PORT")
    port = (
        int(port_env)
        if port_env and port_env not in ("", "0")
        else _find_free_port()
    )
    headless = os.getenv("BROWSER_USE_HEADLESS", "true").lower() != "false"
    user_data_dir = os.getenv(
        "BROWSER_USER_DATA_DIR",
        tempfile.mkdtemp(prefix="browser-use-user-data-dir-"),
    )
    os.makedirs(user_data_dir, exist_ok=True)

    cdp_url    = f"http://localhost:{port}"
    config_dir = os.path.join(tempfile.gettempdir(), f"browser_use_cfg_{port}")

    print(
        f"Bridge: port={port}  headless={headless}  "
        f"user_data_dir={user_data_dir}  cdp_url={cdp_url}",
        file=sys.stderr,
    )

    # ── Write config BEFORE importing browser-use (FIX 6) ────────────────────
    _write_browser_use_config(config_dir, cdp_url, user_data_dir)
    os.environ["BROWSER_USE_CONFIG_DIR"] = config_dir
    os.environ["BROWSER_CDP_URL"]        = cdp_url
    os.environ["MCP_BROWSER_CDP_URL"]    = cdp_url

    # ── Shared Event ──────────────────────────────────────────────────────────
    chrome_ready: asyncio.Event = asyncio.Event()

    # ── Launch Chrome ─────────────────────────────────────────────────────────
    chrome_proc: Optional[asyncio.subprocess.Process] = None

    async def _start_chrome_background() -> None:
        nonlocal chrome_proc
        try:
            chrome_proc = await _launch_chrome(port, user_data_dir, headless)

            # FIX 2: drain stderr in parallel so crash messages are visible
            asyncio.create_task(_drain_stderr(chrome_proc))

            ready = await _wait_for_cdp(port, chrome_proc, timeout_secs=90)
            if ready:
                print(f"Bridge: Chrome CDP ready at {cdp_url}", file=sys.stderr)
            else:
                print(
                    f"Bridge: Chrome CDP NOT ready after 90 s "
                    f"(returncode={chrome_proc.returncode})",
                    file=sys.stderr,
                )
        except Exception as exc:
            print(f"Bridge: Chrome launch error — {exc!r}", file=sys.stderr)
        finally:
            # Always unblock the patch (FIX 1 / FIX 4)
            chrome_ready.set()

    # FIX 4: create the task BEFORE patching and before mcp_main
    chrome_task = asyncio.create_task(_start_chrome_background())

    # Yield control so the task scheduler can start the Chrome coroutine
    await asyncio.sleep(0)

    # ── Patch ─────────────────────────────────────────────────────────────────
    _patch_mcp_server_session_retry(chrome_ready)

    # ── Import mcp_main AFTER config env vars are set (FIX 6) ─────────────────
    from browser_use.mcp.server import main as mcp_main  # type: ignore

    # ── Start browser-use MCP server ──────────────────────────────────────────
    try:
        print("Bridge: starting browser-use MCP server...", file=sys.stderr)
        if inspect.iscoroutinefunction(mcp_main):
            await mcp_main()
        else:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, mcp_main)
    except Exception as exc:
        print(f"Bridge: MCP server error — {exc!r}", file=sys.stderr)
    finally:
        print("Bridge: shutting down...", file=sys.stderr)
        chrome_task.cancel()
        try:
            await chrome_task
        except (asyncio.CancelledError, Exception):
            pass

        if chrome_proc is not None:
            if chrome_proc.returncode is None:
                try:
                    chrome_proc.terminate()
                    await asyncio.wait_for(chrome_proc.wait(), timeout=5)
                except Exception:
                    chrome_proc.kill()
        print("Bridge: cleanup complete", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(run_bridge())