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
    
    print(f"Bridge starting. CDP: {cdp_url}, Own: {own_browser}, UserData: {user_data_dir}", file=sys.stderr)
    
    # If we are connecting to an existing browser, we don't need to launch one here.
    # We just ensure the environment variables are set for the MCP server's internal Agent.
    if cdp_url and own_browser:
        os.environ["BROWSER_CDP_URL"] = cdp_url
        print(f"Bridge configured to connect to: {cdp_url}", file=sys.stderr)
    elif user_data_dir:
        # If we have a unique user data dir, we let the MCP server launch its own isolated browser.
        # This prevents the "two browsers" issue where we launch one and the server launches another.
        os.environ["BROWSER_USER_DATA_DIR"] = user_data_dir
        print(f"Bridge configured with isolated UserData: {user_data_dir}", file=sys.stderr)

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

if __name__ == "__main__":
    asyncio.run(run_bridge())
            

