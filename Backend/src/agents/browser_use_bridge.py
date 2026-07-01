import os
import sys
import asyncio
import socket
import tempfile

# ---------------------------------------------------------------------------
# Chrome binary (Playwright-managed Chromium in the Replit sandbox)
# ---------------------------------------------------------------------------

CHROME_BINARY = (
    "/home/runner/workspace/.cache/ms-playwright"
    "/chromium-1228/chrome-linux64/chrome"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


async def _wait_for_cdp(port: int, timeout_secs: int = 90) -> bool:
    """Poll http://localhost:PORT/json/version until Chrome answers."""
    import aiohttp
    url = f"http://localhost:{port}/json/version"
    for _ in range(timeout_secs):
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.get(url, timeout=aiohttp.ClientTimeout(total=1)) as resp:
                    if resp.status == 200:
                        return True
        except Exception:
            pass
        await asyncio.sleep(1)
    return False


# ---------------------------------------------------------------------------
# Chrome subprocess launch
# ---------------------------------------------------------------------------

async def _launch_chrome(port: int, user_data_dir: str, headless: bool) -> asyncio.subprocess.Process:
    args = [
        CHROME_BINARY,
        f"--remote-debugging-port={port}",
        "--remote-allow-origins=*",
        "--no-sandbox",
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

    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    print(f"Bridge: Chrome launched — pid={proc.pid}  port={port}", file=sys.stderr)
    return proc


# ---------------------------------------------------------------------------
# Monkey-patch: wait for Chrome + reset browser_session on failure
# ---------------------------------------------------------------------------

def _patch_mcp_server_session_retry(chrome_ready: asyncio.Event) -> None:
    """
    Two-part patch on BrowserUseServer._init_browser_session:

    Part 1 — wait for Chrome:
        Awaits chrome_ready (set once /json/version returns 200) before
        calling original().  Prevents "connection refused" on first tool call.

    Part 2 — reset on failure:
        If original() raises, resets self.browser_session = None so the next
        tool call creates a fresh BrowserSession instead of reusing the broken
        one (which would leave _cdp_client_root=None permanently).
    """
    try:
        from browser_use.mcp.server import BrowserUseServer
    except ImportError:
        print("Bridge: BrowserUseServer not importable — skipping patch", file=sys.stderr)
        return

    if not hasattr(BrowserUseServer, "_init_browser_session"):
        print("Bridge: _init_browser_session not found — skipping patch", file=sys.stderr)
        return

    original = BrowserUseServer._init_browser_session

    async def _patched_init(self, allowed_domains: "list[str] | None" = None, **kwargs):
        # Part 1: block until Chrome is confirmed ready
        if not chrome_ready.is_set():
            print("Bridge [patch]: waiting for Chrome...", file=sys.stderr)
            try:
                await asyncio.wait_for(chrome_ready.wait(), timeout=90.0)
                print("Bridge [patch]: Chrome ready — connecting", file=sys.stderr)
            except asyncio.TimeoutError:
                print("Bridge [patch]: 90 s timeout — trying anyway", file=sys.stderr)

        # Part 2: reset broken session so next tool call retries
        try:
            await original(self, allowed_domains=allowed_domains, **kwargs)
        except Exception as exc:
            self.browser_session = None
            print(
                f"Bridge [patch]: _init_browser_session failed ({exc!r}) — "
                "reset browser_session=None for retry",
                file=sys.stderr,
            )
            raise

    BrowserUseServer._init_browser_session = _patched_init  # type: ignore[method-assign]
    print("Bridge: _init_browser_session patched (chrome-wait + retry-on-fail)", file=sys.stderr)


# ---------------------------------------------------------------------------
# Main bridge coroutine
# ---------------------------------------------------------------------------

async def run_bridge():
    from browser_use.mcp.server import main
    import inspect

    # -- Read env vars set by MCPToolManager ----------------------------------
    cdp_url_env  = os.getenv("MCP_BROWSER_CDP_URL") or os.getenv("BROWSER_CDP_URL")
    own_browser  = os.getenv("MCP_BROWSER_USE_OWN_BROWSER", "false").lower() == "true"
    port_env     = os.getenv("BROWSER_USE_CDP_PORT")
    port         = int(port_env) if port_env and port_env not in ("", "0") else find_free_port()
    headless     = os.getenv("BROWSER_USE_HEADLESS", "true").lower() != "false"
    user_data_dir = os.getenv(
        "BROWSER_USER_DATA_DIR",
        tempfile.mkdtemp(prefix="browser-use-user-data-dir-"),
    )
    os.makedirs(user_data_dir, exist_ok=True)

    cdp_url = cdp_url_env or f"http://localhost:{port}"

    print(
        f"Bridge: port={port}  headless={headless}  own_browser={own_browser}  "
        f"cdp_url={cdp_url}  user_data_dir={user_data_dir}",
        file=sys.stderr,
    )

    # -- Shared Event: set when Chrome is confirmed ready ---------------------
    chrome_ready = asyncio.Event()
    chrome_proc: asyncio.subprocess.Process | None = None

    if own_browser:
        # We own Chrome: launch it ourselves in the background.
        # The patch will await chrome_ready before attempting BrowserSession.start().
        async def _start_chrome_background() -> None:
            nonlocal chrome_proc
            print("Bridge: launching Chrome in background...", file=sys.stderr)
            try:
                chrome_proc = await _launch_chrome(port, user_data_dir, headless)

                # Drain stderr in background so the pipe buffer never fills
                async def _drain_stderr():
                    assert chrome_proc.stderr
                    while True:
                        line = await chrome_proc.stderr.readline()
                        if not line:
                            break
                        print(f"Chrome stderr: {line.decode(errors='replace').rstrip()}", file=sys.stderr)
                asyncio.create_task(_drain_stderr())

                # Watch for early exit
                async def _watch_exit():
                    code = await chrome_proc.wait()
                    if not chrome_ready.is_set():
                        print(f"Bridge: Chrome exited with code {code} before becoming ready", file=sys.stderr)
                        chrome_ready.set()  # unblock patch so it can fail fast
                asyncio.create_task(_watch_exit())

                ready = await _wait_for_cdp(port, timeout_secs=90)
                if ready:
                    print(f"Bridge: Chrome ready at {cdp_url}", file=sys.stderr)
                else:
                    print("Bridge: Chrome CDP not ready after 90 s", file=sys.stderr)
            except Exception as exc:
                print(f"Bridge: Chrome launch error — {exc}", file=sys.stderr)
            finally:
                chrome_ready.set()  # always unblock

        asyncio.create_task(_start_chrome_background())

        # Export CDP URL for browser-use and screenshotter
        os.environ["BROWSER_CDP_URL"]     = cdp_url
        os.environ["MCP_BROWSER_CDP_URL"] = cdp_url

    else:
        # External Chrome already running; signal ready immediately
        print(f"Bridge: connecting to existing browser at {cdp_url}", file=sys.stderr)
        chrome_ready.set()

    # -- Apply patches --------------------------------------------------------
    _patch_mcp_server_session_retry(chrome_ready)

    # -- Start browser-use MCP server (blocking) ------------------------------
    try:
        print("Bridge: starting browser-use MCP server...", file=sys.stderr)
        if inspect.iscoroutinefunction(main):
            await main()
        else:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, main)
    except Exception as exc:
        print(f"Bridge: MCP server error — {exc}", file=sys.stderr)
    finally:
        print("Bridge: shutting down...", file=sys.stderr)
        if chrome_proc is not None:
            try:
                chrome_proc.terminate()
                await asyncio.wait_for(chrome_proc.wait(), timeout=5)
            except Exception:
                chrome_proc.kill()
        print("Bridge: cleanup complete", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(run_bridge())
