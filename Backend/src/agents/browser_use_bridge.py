import os
import sys
import asyncio
import glob as _glob
from browser_use.mcp.server import main

# ── Chromium binary resolution ────────────────────────────────────────────────
# Prefer an explicit override, then fall back to the Playwright-installed build.
def _find_chromium() -> str | None:
    override = os.getenv("BROWSER_EXECUTABLE_PATH")
    if override and os.path.isfile(override):
        return override
    # Look for the Playwright-downloaded full Chrome (not headless-shell)
    patterns = [
        os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux64/chrome"),
        "/home/runner/workspace/.cache/ms-playwright/chromium-*/chrome-linux64/chrome",
    ]
    for pattern in patterns:
        matches = sorted(_glob.glob(pattern))
        if matches:
            return matches[-1]  # newest version
    return None  # let browser-use find its own default

# Required args for headless Chromium in a sandboxed Linux environment (Replit/CI)
_SANDBOX_ARGS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-setuid-sandbox",
    "--remote-allow-origins=*",
]

async def run_bridge():
    port_env = os.getenv("BROWSER_USE_CDP_PORT")
    port = int(port_env) if port_env and port_env != "0" else 9222
    user_data_dir = os.getenv("BROWSER_USER_DATA_DIR")
    headless = os.getenv("BROWSER_USE_HEADLESS", "true").lower() != "false"
    chromium_path = _find_chromium()

    print(
        f"Bridge starting — port={port}, headless={headless}, "
        f"user_data_dir={user_data_dir}, chromium={chromium_path}",
        file=sys.stderr,
    )

    browser = None
    try:
        from browser_use import BrowserSession, BrowserProfile

        profile_kwargs = dict(
            headless=headless,
            args=_SANDBOX_ARGS + [f"--remote-debugging-port={port}"],
            disable_security=True,
        )
        if chromium_path:
            profile_kwargs["executable_path"] = chromium_path
        if user_data_dir:
            profile_kwargs["user_data_dir"] = user_data_dir

        profile = BrowserProfile(**profile_kwargs)
        browser = BrowserSession(browser_profile=profile)
        await browser.start()

        cdp_url = f"http://localhost:{port}"
        os.environ["BROWSER_CDP_URL"] = cdp_url
        os.environ["MCP_BROWSER_CDP_URL"] = cdp_url
        print(f"Bridge launched browser at: {cdp_url}", file=sys.stderr)

    except Exception as e:
        print(f"Bridge: failed to launch browser — {e}", file=sys.stderr)
        # Continue anyway: the MCP server may still work if a browser is already up

    try:
        print("Bridge: starting MCP server...", file=sys.stderr)
        import inspect
        if inspect.iscoroutinefunction(main):
            await main()
        else:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, main)
    except Exception as e:
        print(f"Bridge: MCP server error — {e}", file=sys.stderr)
    finally:
        if browser:
            try:
                await browser.close()
            except Exception:
                pass

if __name__ == "__main__":
    asyncio.run(run_bridge())
            

