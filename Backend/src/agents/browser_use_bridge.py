import os
import sys
import socket
import asyncio
import logging
from pathlib import Path

# ---------------------------------------------------------------------------
# CRITICAL: Redirect ALL logging to stderr BEFORE any other imports.
# The MCP stdio transport uses stdout exclusively for JSON-RPC messages.
# Any non-JSON bytes written to stdout (e.g. Python logging, browser-use
# INFO lines like "Setting viewport to...") will corrupt the framing and
# cause the MCP client to throw anyio.BrokenResourceError.
# ---------------------------------------------------------------------------
_stderr_handler = logging.StreamHandler(sys.stderr)
_stderr_handler.setFormatter(logging.Formatter("%(levelname)-8s [%(name)s] %(message)s"))
logging.root.handlers = [_stderr_handler]
logging.root.setLevel(logging.WARNING)  # Suppress verbose INFO from browser-use in bridge

# Silence the specific noisy browser-use loggers entirely in this subprocess
for _noisy in ("browser_use", "BrowserSession", "playwright", "urllib3", "httpx"):
    logging.getLogger(_noisy).setLevel(logging.ERROR)

# Add parent directory to path for config imports
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from src import config
    # After importing config (which calls logging.basicConfig via logger.py),
    # re-apply our stderr-only override so that basicConfig doesn't sneak
    # a stdout handler back in.
    logging.root.handlers = [_stderr_handler]
except ImportError:
    class MockConfig:
        BROWSER_CDP_READY_TIMEOUT_SECONDS = 90
        BROWSER_DEFAULT_CDP_HOST = "127.0.0.1"
        def browser_user_data_dir_override(self, default): return os.getenv("BROWSER_USER_DATA_DIR", default)
    config = MockConfig()

# ---------------------------------------------------------------------------
# Stealth JS
# ---------------------------------------------------------------------------
STEALTH_JS = """
(function() {
    try {
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined, configurable: true });
    } catch(e) {}
    try { delete window.__playwright; delete window.__pwInitScripts; delete window.__PWDEBUGGER__; } catch(e) {}
    try {
        Object.getOwnPropertyNames(window).forEach(function(key) {
            if (key.startsWith('cdc_')) { try { delete window[key]; } catch(e) {} }
        });
    } catch(e) {}
    try {
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'], configurable: true });
    } catch(e) {}
})();
"""

# ---------------------------------------------------------------------------
# Monkey-patch BrowserUseServer
# ---------------------------------------------------------------------------

def find_free_port() -> int:
    """Dynamically finds an available free port on the host machine."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

def _patch_mcp_server(browser_session: 'BrowserSession', get_cdp_url_func, headless: bool, proxy_url: str = ""):
    try:
        from browser_use.mcp.server import BrowserUseServer
        from browser_use.browser import BrowserSession, BrowserProfile
        import mcp.types as mcp_types
    except ImportError as e:
        print(f"Bridge: import error: {e}. Are you using the correct fork of browser-use?", file=sys.stderr)
        return

    _headless = headless
    _proxy_url = proxy_url

    # 1. Patch session initialization to connect to the dynamically discovered CDP URL
    async def _patched_init(self, allowed_domains: list[str] | None = None, **kwargs):
        if getattr(self, "browser_session", None):
            return

        # print(f"Bridge [patch]: binding MCP server to active BrowserSession", file=sys.stderr)
        try:
            self.browser_session = browser_session
            
            # Create tools for direct actions (required so MCP tool functions execute against this session)
            from browser_use import Tools
            self.tools = Tools()



            # Initialize FileSystem for extraction actions
            try:
                from browser_use.mcp.server import get_default_profile, FileSystem
                profile_config = get_default_profile(self.config)
                file_system_path = profile_config.get('file_system_path', '~/.browser-use-mcp')
                self.file_system = FileSystem(base_dir=Path(file_system_path).expanduser())
            except Exception as e:
                print(f"Bridge [patch]: FileSystem initialization warning: {e}", file=sys.stderr)

            if hasattr(self, '_track_session'):
                self._track_session(self.browser_session)
        except Exception as exc:
            self.browser_session = None
            self.tools = None
            print(f"Bridge [patch]: session binding failed: {exc}", file=sys.stderr)
            raise

    BrowserUseServer._init_browser_session = _patched_init

    # 2. Add missing tools: browser_key_press and browser_wait
    NEW_TOOL_SCHEMAS = [
        mcp_types.Tool(
            name="browser_key_press",
            description="Press a keyboard key or combination (e.g. 'Enter', 'Control+A').",
            inputSchema={
                "type": "object",
                "properties": {"key": {"type": "string"}},
                "required": ["key"],
            },
        ),
        mcp_types.Tool(
            name="browser_wait",
            description="Wait for N milliseconds.",
            inputSchema={
                "type": "object",
                "properties": {"milliseconds": {"type": "integer", "default": 500}},
            },
        ),
    ]

    async def _exec_key_press(srv, args: dict) -> str:
        if not srv.browser_session: await srv._init_browser_session()
        key = str(args.get("key", "Enter"))
        try:
            page = await srv.browser_session.get_current_page()
            # FIX: Used page.keyboard.press instead of page.press
            await page.keyboard.press(key)
            return f"Pressed: {key}"
        except Exception as e: 
            return f"Error: {e}"

    async def _exec_wait(srv, args: dict) -> str:
        ms = int(args.get("milliseconds", 500))
        await asyncio.sleep(ms / 1000.0)
        return f"Waited {ms}ms"

    _orig_execute = BrowserUseServer._execute_tool
    async def _patched_execute_tool(self, tool_name: str, arguments: dict):
        if tool_name == "browser_key_press": return await _exec_key_press(self, arguments)
        if tool_name == "browser_wait": return await _exec_wait(self, arguments)
        return await _orig_execute(self, tool_name, arguments)

    BrowserUseServer._execute_tool = _patched_execute_tool

    _orig_setup = BrowserUseServer._setup_handlers
    def _patched_setup_handlers(self):
        _orig_setup(self)
        orig_lt = self.server.request_handlers.get(mcp_types.ListToolsRequest)
        if orig_lt:
            async def _extended_list_tools(req):
                result = await orig_lt(req)
                if isinstance(result, mcp_types.ListToolsResult):
                    result.tools = list(result.tools) + NEW_TOOL_SCHEMAS
                return result
            self.server.request_handlers[mcp_types.ListToolsRequest] = _extended_list_tools

    BrowserUseServer._setup_handlers = _patched_setup_handlers
    # print("Bridge: BrowserUseServer patched with CDP and tools", file=sys.stderr)

# ---------------------------------------------------------------------------
# Main Execution
# ---------------------------------------------------------------------------

async def run_bridge():
    # 1. Config
    headless = os.getenv("BROWSER_USE_HEADLESS", "true").lower() != "false"
    proxy_url = os.getenv("BROWSER_PROXY_URL", "")
    _default_profile = str(Path.home() / ".config" / "browser-use" / "profile")
    user_data_dir = config.browser_user_data_dir_override(_default_profile)
    os.makedirs(user_data_dir, exist_ok=True)

    # 2. Launch Browser via browser-use (is_local=True)
    # print(f"Bridge: launching browser via browser-use...", file=sys.stderr)
    from browser_use.browser import BrowserSession, BrowserProfile

    port_env = os.getenv("BROWSER_USE_CDP_PORT")
    if not port_env or port_env == "0":
        # Fallback only if the manager failed to provide one
        port = find_free_port()
    else:
        port = int(port_env)
    
    # print(f"Bridge using port: {port}", file=sys.stderr)

    keep_alive = os.getenv("BROWSER_USE_KEEP_ALIVE", "true").lower() != "false"
    if "--keep-alive" in sys.argv:
        keep_alive = True
    elif "--no-keep-alive" in sys.argv:
        keep_alive = False

    engine = os.getenv("BROWSER_ENGINE", "chrome").lower()
    executable_path = os.getenv("BROWSER_EXECUTABLE_PATH")

    if engine == "camoufox":
        import json
        # Since Firefox/Camoufox does not implement the /json/version endpoint required by cdp-use,
        # we write a fallback flag so brain.py can notify the UI and fall back to Chrome.
        fallback_flag = f"/tmp/camoufox_fallback_{port}.json"
        try:
            os.makedirs(os.path.dirname(fallback_flag), exist_ok=True)
            with open(fallback_flag, "w") as f:
                json.dump({
                    "reason": "Camoufox (Firefox) CDP format is not supported by browser-use. Automatically fell back to Chrome."
                }, f)
        except Exception:
            pass
        print("Bridge [Camoufox]: Camoufox (Firefox) is not supported via browser-use CDP. Falling back to Chrome.", file=sys.stderr)
        engine = "chrome"

    profile = BrowserProfile(
        headless=headless,
        user_data_dir=user_data_dir,
        chromium_args=[
            "--remote-allow-origins=*",
            f"--remote-debugging-port={port}",
        ],
        proxy={'server': proxy_url} if proxy_url else None,
        keep_alive=keep_alive,
        executable_path=executable_path if executable_path else None
    )
    browser_session = BrowserSession(browser_profile=profile, keep_alive=keep_alive)
    await browser_session.start()

    # Inject Stealth JS
    try:
        page = await browser_session.get_current_page()
        await page.add_init_script(STEALTH_JS)
    except Exception as e:
        print(f"Bridge: Stealth JS injection failed: {e}", file=sys.stderr)
    
    cdp_url = f"http://localhost:{port}"
    os.environ["BROWSER_CDP_URL"] = cdp_url
    os.environ["MCP_BROWSER_CDP_URL"] = cdp_url

    # print(f"Bridge: browser launched at {cdp_url}", file=sys.stderr)

    async def get_cdp_url():
        return cdp_url

    # 3. Patch and Start MCP Server
    _patch_mcp_server(browser_session, get_cdp_url, headless, proxy_url)
    
    try:
        from browser_use.mcp.server import main
        import inspect
        # print("Bridge: starting MCP server...", file=sys.stderr)
        if inspect.iscoroutinefunction(main):
            await main()
        else:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, main)
    except KeyboardInterrupt:
        print("Bridge: Shutting down...", file=sys.stderr)
    finally:
        try:
            await browser_session.kill()
        except Exception:
            pass
        if camoufox_instance:
            try:
                await camoufox_instance.__aexit__(None, None, None)
            except Exception:
                pass

if __name__ == "__main__":
    asyncio.run(run_bridge())