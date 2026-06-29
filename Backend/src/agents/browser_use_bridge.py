import os
import sys
import asyncio
import socket
from browser_use import Browser
from browser_use.mcp.server import main

def find_free_port() -> int:
    """Dynamically finds an available free port on the host machine."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

async def run_bridge():
    # 1. Check for existing CDP URL or manual Chrome config
    cdp_url = os.getenv("MCP_BROWSER_CDP_URL") or os.getenv("BROWSER_CDP_URL")
    own_browser = os.getenv("MCP_BROWSER_USE_OWN_BROWSER", "false").lower() == "true"
    
    # Manual config support
    executable_path = os.getenv("BROWSER_EXECUTABLE_PATH")
    user_data_dir = os.getenv("BROWSER_USER_DATA_DIR")
    port_env = os.getenv("BROWSER_USE_CDP_PORT")
    port = int(port_env) if port_env and port_env != "0" else 9222
    
    print(f"Bridge starting. CDP: {cdp_url}, Own: {own_browser}, UserData: {user_data_dir}, Port: {port}", file=sys.stderr)
    
    browser = None
    # If we are connecting to an existing browser, we don't need to launch one here.
    if cdp_url and own_browser:
        os.environ["BROWSER_CDP_URL"] = cdp_url
        print(f"Bridge configured to connect to: {cdp_url}", file=sys.stderr)
    else:
        # If we don't have an existing browser to connect to, we MUST launch one
        # so that the MCP server has a browser to interact with and take screenshots from.
        print(f"Launching new browser for MCP server on port {port}...", file=sys.stderr)
        try:
            from browser_use import BrowserSession, BrowserProfile

            profile = BrowserProfile(
                headless=os.getenv("BROWSER_USE_HEADLESS", "false").lower() == "true",
                chromium_args=[
                    "--remote-allow-origins=*",
                    f"--remote-debugging-port={port}",
                ],
            )

            browser = BrowserSession(
                browser_profile=profile
            )

            await browser.start()

            cdp_url = f"http://localhost:{port}"
            os.environ["BROWSER_CDP_URL"] = cdp_url
            os.environ["MCP_BROWSER_CDP_URL"] = cdp_url

            print(f"Bridge launched browser at: {cdp_url}", file=sys.stderr)
        except Exception as e:
            print(f"Failed to launch browser in bridge: {e}", file=sys.stderr)

    try:
        print(f"Starting MCP server...", file=sys.stderr)
        # Start the MCP server (this is a blocking call)
        import inspect
        if inspect.iscoroutinefunction(main):
            await main()
        else:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, main)
    
    except Exception as e:
        print(f"Bridge Error: {e}", file=sys.stderr)
    finally:
        if browser:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run_bridge())
            

