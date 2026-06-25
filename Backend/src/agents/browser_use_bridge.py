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
    cdp_url = os.getenv("MCP_BROWSER_CDP_URL")
    own_browser = os.getenv("MCP_BROWSER_USE_OWN_BROWSER", "false").lower() == "true"
    
    # Manual config support from code.txt
    executable_path = os.getenv("BROWSER_EXECUTABLE_PATH")
    user_data_dir = os.getenv("BROWSER_USER_DATA_DIR")
    profile_directory = os.getenv("BROWSER_PROFILE_DIRECTORY", "Default")
    
    # 2. Launch new browser if no CDP or not requested to use own
    port_env = os.getenv("BROWSER_USE_CDP_PORT")
    port = int(port_env) if port_env and port_env != "0" else 0
    
    if port == 0:
        port = find_free_port()
    
    print(f"Bridge using port: {port}", file=sys.stderr)
    
    common_args = [
        f"--remote-debugging-port={port}",
        "--remote-allow-origins=*",
        "--test-type", # Hides the "unsupported flag" warning
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-blink-features=AutomationControlled"
    ]

    browser = None
    try:
        if cdp_url and own_browser:
            print(f"Connecting to existing browser at: {cdp_url}", file=sys.stderr)
            browser = Browser(cdp_url=cdp_url)
        elif executable_path and user_data_dir:
            print(f"Attempting to launch system Chrome from: {executable_path} on port {port}", file=sys.stderr)
            # Add profile directory if specified
            if profile_directory:
                common_args.append(f"--profile-directory={profile_directory}")
                
            browser = Browser(
                executable_path=executable_path,
                user_data_dir=user_data_dir,
                args=common_args,
                headless=os.getenv("BROWSER_USE_HEADLESS", "false").lower() == "true"
            )
            cdp_url = f"http://localhost:{port}"
        else:
            raise ValueError("No system browser config found, falling back to isolated browser.")
            
        # Start/Connect the browser
        await browser.start()
        
    except Exception as e:
        print(f"System Browser Connection Failed: {e}. Falling back to new isolated browser.", file=sys.stderr)
        # Fallback logic
        browser = Browser(
            headless=os.getenv("BROWSER_USE_HEADLESS", "false").lower() == "true",
            args=common_args
        )
        cdp_url = f"http://localhost:{port}"
        await browser.start()
    
    try:
        # Ensure the CDP URL is available for the MCP server
        os.environ["MCP_BROWSER_CDP_URL"] = cdp_url
        
        print(f"Browser-Use active. CDP URL: {cdp_url}", file=sys.stderr)

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
    try:
        asyncio.run(run_bridge())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Fatal Bridge Error: {e}", file=sys.stderr)
        sys.exit(1)
