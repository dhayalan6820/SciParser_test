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
    // 1. Webdriver
    try { Object.defineProperty(navigator, 'webdriver', { get: () => undefined, configurable: true }); } catch(e) {}
    
    // 2. Playwright markers
    try { delete window.__playwright; delete window.__pwInitScripts; delete window.__PWDEBUGGER__; } catch(e) {}
    try { Object.getOwnPropertyNames(window).forEach(function(key) { if (key.startsWith('cdc_')) { try { delete window[key]; } catch(e) {} } }); } catch(e) {}
    
    // 3. Languages
    try { Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'], configurable: true }); } catch(e) {}
    
    // 4. Plugins
    try {
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3], // Mock length to bypass empty check
            configurable: true
        });
    } catch(e) {}
    
    // 5. Chrome runtime object
    try {
        window.chrome = {
            runtime: {},
            loadTimes: function() {},
            csi: function() {},
            app: {}
        };
    } catch(e) {}
    
    // 6. Permissions API
    try {
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = parameters => (
            parameters.name === 'notifications' ?
            Promise.resolve({ state: Notification.permission }) :
            originalQuery(parameters)
        );
    } catch(e) {}
    
    // 7. OuterHeight / OuterWidth (Playwright defaults to 0 in headless)
    try {
        if (window.outerWidth === 0) {
            Object.defineProperty(window, 'outerWidth', { get: () => window.innerWidth, configurable: true });
            Object.defineProperty(window, 'outerHeight', { get: () => window.innerHeight, configurable: true });
        }
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

            # Initialize LLM for extraction
            try:
                from langchain_openai import ChatOpenAI
                import os
                api_key = os.environ.get("OPENAI_API_KEY")
                base_url = os.environ.get("OPENAI_BASE_URL")
                model = os.environ.get("BROWSER_USE_MODEL", "gpt-4o-mini")
                if api_key:
                    kwargs_llm = {}
                    if base_url: kwargs_llm["base_url"] = base_url
                    self.llm = ChatOpenAI(model=model, api_key=api_key, **kwargs_llm)
                else:
                    self.llm = None
            except Exception as e:
                print(f"Bridge [patch]: LLM init warning: {e}", file=sys.stderr)
                self.llm = None

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
        mcp_types.Tool(
            name="browser_extract_raw",
            description="Extract data from a page by bypassing the DOM accessibility tree. Best used when 'browser_extract_content' fails due to non-semantic HTML.",
            inputSchema={
                "type": "object",
                "properties": {"query": {"type": "string", "description": "What to extract (e.g. 'All laptop stands with price and rating')."}},
                "required": ["query"],
            },
        ),
        mcp_types.Tool(
            name="browser_extract_vision",
            description="Extract data using a screenshot and Vision LLM. Best used as a last resort when DOM/Raw extraction fails entirely (e.g., bot protection, canvas rendering, empty lists).",
            inputSchema={
                "type": "object",
                "properties": {"query": {"type": "string", "description": "What to extract (e.g. 'All products with name and price from this image')."}},
                "required": ["query"],
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

    async def _exec_extract_raw(srv, args: dict) -> str:
        if not srv.browser_session: await srv._init_browser_session()
        query = args.get("query", "")
        try:
            page = await srv.browser_session.get_current_page()
            # Prune junk elements temporarily to get clean text and reduce tokens
            js_script = """
            () => {
                let junk = document.querySelectorAll('script, style, svg, iframe, noscript, nav, footer, header, aside, form, [style*="display: none"], [style*="visibility: hidden"]');
                let hiddenStates = [];
                junk.forEach(n => {
                    hiddenStates.push(n.style.display);
                    n.style.display = 'none';
                });
                
                let mainNode = document.querySelector('main') || document.body;
                let text = mainNode.innerText || "";
                
                junk.forEach((n, i) => {
                    n.style.display = hiddenStates[i];
                });
                
                return text.split('\\n').map(l => l.trim()).filter(l => l.length > 0).join('\\n');
            }
            """
            raw_text = await page.evaluate(js_script)
            
            if not srv.llm:
                return f"Error: No LLM configured in bridge to parse raw text. Raw text length: {len(raw_text)}"
            
            from langchain_core.messages import HumanMessage
            prompt = (
                f"You are a Data Extractor. Extract the following information from the raw page text:\n"
                f"QUERY: {query}\n\n"
                f"PAGE TEXT:\n{raw_text[:12000]}\n\n"
                f"Return ONLY valid JSON. Return an array of objects if there are multiple matches."
            )
            resp = await srv.llm.ainvoke([HumanMessage(content=prompt)])
            return resp.content
        except Exception as e:
            return f"Error extracting raw text: {e}"

    async def _exec_extract_vision(srv, args: dict) -> str:
        if not srv.browser_session: await srv._init_browser_session()
        query = args.get("query", "")
        try:
            page = await srv.browser_session.get_current_page()
            b64_image = await page.screenshot(format='png')
            
            if not srv.llm:
                return "Error: No LLM configured in bridge to parse screenshot."
            
            from langchain_core.messages import HumanMessage
            prompt = (
                f"You are a Data Extractor. Extract the following information purely from the provided image of a webpage:\n"
                f"QUERY: {query}\n\n"
                f"Return ONLY valid JSON. Return an array of objects if there are multiple matches."
            )
            msg = HumanMessage(content=[
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_image}"}}
            ])
            resp = await srv.llm.ainvoke([msg])
            return resp.content
        except Exception as e:
            return f"Error extracting via vision: {e}"

    _orig_execute = BrowserUseServer._execute_tool
    async def _patched_execute_tool(self, tool_name: str, arguments: dict):
        if tool_name == "browser_key_press": return await _exec_key_press(self, arguments)
        if tool_name == "browser_wait": return await _exec_wait(self, arguments)
        if tool_name == "browser_extract_raw": return await _exec_extract_raw(self, arguments)
        if tool_name == "browser_extract_vision": return await _exec_extract_vision(self, arguments)
        return await _orig_execute(self, tool_name, arguments)

    BrowserUseServer._execute_tool = _patched_execute_tool

    _orig_setup = BrowserUseServer._setup_handlers
    def _patched_setup_handlers(self):
        _orig_setup(self)
        orig_lt = self.server.request_handlers.get(mcp_types.ListToolsRequest)
        if orig_lt:
            async def _extended_list_tools(req):
                result = await orig_lt(req)
                if hasattr(result, 'root') and isinstance(result.root, mcp_types.ListToolsResult):
                    result.root.tools = list(result.root.tools) + NEW_TOOL_SCHEMAS
                elif isinstance(result, mcp_types.ListToolsResult):
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
    # Initialise to None so the finally block never hits NameError when the
    # Camoufox branch falls back to Chrome without assigning the variable.
    camoufox_instance = None

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

    use_system_chrome = os.getenv("BROWSER_USE_SYSTEM_CHROME", "false").lower() == "true"
    system_chrome_profile = os.getenv("BROWSER_USE_PROFILE_DIR", "Default")

    if use_system_chrome:
        import socket
        port = 9222  # System Chrome default CDP port
        
        def is_port_open(port):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1.0)
                    return s.connect_ex(('localhost', port)) == 0
            except Exception:
                return False

        if not is_port_open(port):
            print("Bridge: System Chrome debug port 9222 is not open. Automatically falling back to normal Chromium.", file=sys.stderr)
            use_system_chrome = False

    if use_system_chrome:
        from browser_use import Browser
        print(f"Bridge: Using system Chrome with profile: {system_chrome_profile}", file=sys.stderr)
        browser_session = Browser.from_system_chrome(profile_directory=system_chrome_profile)
        await browser_session.start()
    else:
        profile = BrowserProfile(
            headless=headless,
            user_data_dir=user_data_dir,
            chromium_args=[
                "--remote-allow-origins=*",
                f"--remote-debugging-port={port}",
                "--no-first-run",
                "--no-default-browser-check",
                "--skip-first-run-ui",
                "--disable-search-engine-choice-screen",
                "--disable-features=Translate,OptimizationHints"
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
        from browser_use.mcp.server import BrowserUseServer
        import logging
        logging.disable(logging.NOTSET) # Restore logging
        from mcp.server.stdio import stdio_server
        from mcp.server.models import InitializationOptions
        from mcp.server import NotificationOptions
        from browser_use.utils import get_browser_use_version

        # Instantiate server directly
        mcp_srv = BrowserUseServer()
        mcp_srv.browser_session = browser_session

        version = "0.1.0"
        try:
            version = get_browser_use_version()
        except Exception:
            pass

        init_options = InitializationOptions(
            server_name="browser-use",
            server_version=version,
            capabilities=mcp_srv.server.get_capabilities(
                notification_options=NotificationOptions(),
                experimental_capabilities={},
            ),
        )

        async with stdio_server() as (read_stream, write_stream):
            await mcp_srv.server.run(
                read_stream,
                write_stream,
                init_options
            )
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