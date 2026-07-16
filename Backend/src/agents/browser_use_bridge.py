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
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
try:
    from src import config
except ImportError as e:
    print(f"Bridge [patch]: Failed to import src.config, using MockConfig: {e}", file=sys.stderr)
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
        if getattr(self, "llm", None) is not None:
            return

        # print(f"Bridge [patch]: binding MCP server to active BrowserSession", file=sys.stderr)
        try:
            self.browser_session = browser_session
            
            # Create tools for direct actions (required so MCP tool functions execute against this session)
            from browser_use import Tools
            self.tools = Tools()

            # Initialize LLM for extraction
            try:
                import os
                
                # FORCE LOAD ENV VARS in this subprocess
                try:
                    from dotenv import load_dotenv
                    env_path = os.path.join(Path(__file__).parent.parent.parent, ".env")
                    load_dotenv(env_path)
                    print(f"Bridge [patch]: Loaded .env from {env_path}", file=sys.stderr)
                except Exception as env_err:
                    print(f"Bridge [patch]: Failed to load .env: {env_err}", file=sys.stderr)

                model = os.environ.get("LLM_EXTRACTION_MODEL") or getattr(config, "LLM_EXTRACTION_MODEL", "openai/gpt-4o-mini-2024-07-18")
                base_url = os.environ.get("OPENAI_BASE_URL") or os.environ.get("OPENAI_API_BASE") or getattr(config, "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
                
                # Try OpenRouter specifically
                if "openrouter" in base_url or "openrouter" in model.lower():
                    api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY") or getattr(config, "OPENROUTER_API_KEY", "")
                else:
                    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENROUTER_API_KEY") or getattr(config, "OPENROUTER_API_KEY", "")
                    
                if api_key:
                    try:
                        from browser_use.llm.openai.chat import ChatOpenAI as BrowserUseChatOpenAI
                        self.llm = BrowserUseChatOpenAI(
                            model=model,
                            api_key=api_key,
                            base_url=base_url,
                            temperature=0.8,
                            max_retries=3,
                        )
                        print("SUCCESS_TOKEN: LLM successfully initialized via browser_use custom ChatOpenAI!", file=sys.stderr)
                    except Exception as fallback_e:
                        print(f"Bridge [patch]: Custom ChatOpenAI init failed, falling back to standard langchain. Reason: {fallback_e}", file=sys.stderr)
                        # Standard langchain fallback as safety
                        from langchain_openai import ChatOpenAI
                        kwargs_llm = {}
                        if base_url:
                            kwargs_llm["base_url"] = base_url
                        try:
                            self.llm = ChatOpenAI(model=model, api_key=api_key, **kwargs_llm)
                        except Exception:
                            self.llm = ChatOpenAI(model=model, openai_api_key=api_key, **kwargs_llm)
                else:
                    self.llm = None
                    print("Bridge [patch]: LLM init FATAL ERROR: No API key found.", file=sys.stderr)
            except Exception as e:
                import traceback
                print(f"Bridge [patch]: LLM init FATAL ERROR:\n{traceback.format_exc()}", file=sys.stderr)
                self.llm = None

            # Initialize FileSystem for extraction actions
            try:
                from browser_use.mcp.server import get_default_profile, FileSystem
                profile_config = get_default_profile(self.config)
                file_system_path = profile_config.get('file_system_path', getattr(config, 'BROWSER_USE_FILE_SYSTEM_PATH', '~/.browser-use-mcp'))
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

    # 2. Add browser_evaluate tool
    NEW_TOOL_SCHEMAS = [
        mcp_types.Tool(
            name="browser_evaluate",
            description="Execute custom JavaScript code on the page (for advanced interactions, shadow DOM, custom selectors, data extraction).",
            inputSchema={
                "type": "object",
                "properties": {"code": {"type": "string", "description": "The JavaScript expression or IIFE to evaluate (e.g. '() => document.body.innerText')."}},
                "required": ["code"],
            },
        ),
    ]

    async def _exec_evaluate(srv, args: dict) -> str:
        if not srv.browser_session: await srv._init_browser_session()
        code = str(args.get("code", ""))
        try:
            page = await srv.browser_session.get_current_page()
            result = await page.evaluate(code)
            return str(result)
        except Exception as e:
            return f"Error executing JavaScript: {e}"

    _orig_execute = BrowserUseServer._execute_tool
    async def _patched_execute_tool(self, tool_name: str, arguments: dict):
        # Force initialization so self.llm is guaranteed to be set
        await self._init_browser_session()
        
        if tool_name == "browser_evaluate": return await _exec_evaluate(self, arguments)
        res = await _orig_execute(self, tool_name, arguments)
        if isinstance(res, str) and "LLM not initialized" in res:
            raise ValueError(res)
        return res

    BrowserUseServer._execute_tool = _patched_execute_tool
    
    # 3. Patch _extract_content to report actual errors or fallback to raw page text
    async def _patched_extract_content(self, query: str, extract_links: bool = False) -> str:
        if not self.llm: return 'Error: LLM not initialized (set OPENAI_API_KEY)'
        if not self.file_system: return 'Error: FileSystem not initialized'
        if not self.browser_session: return 'Error: No browser session active'
        if not self.tools: return 'Error: Tools not initialized'

        from browser_use import ActionModel
        from pydantic import create_model
        from typing import Any

        try:
            ExtractAction = create_model(
                'ExtractAction',
                __base__=ActionModel,
                extract=dict[str, Any],
            )
            action = ExtractAction.model_validate(
                {
                    'extract': {'query': query, 'extract_links': extract_links},
                }
            )
            action_result = await self.tools.act(
                action=action,
                browser_session=self.browser_session,
                page_extraction_llm=self.llm,
                file_system=self.file_system,
            )
            
            # If the tool succeeded and returned actual content, return it!
            if action_result.extracted_content and action_result.extracted_content != 'No content extracted':
                return action_result.extracted_content
                
            # If it failed or returned nothing, execute the fallback (extract visible page text)
            print("Bridge [patch]: LLM extraction returned empty/failed. Attempting javascript fallback...", file=sys.stderr)
            try:
                page = await self.browser_session.get_current_page()
                fallback_text = await page.evaluate("() => document.body.innerText")
                if fallback_text and fallback_text.strip():
                    return f"[Extraction LLM failed, using page text fallback]:\n{fallback_text}"
            except Exception as eval_err:
                print(f"Bridge [patch]: Fallback eval failed: {eval_err}", file=sys.stderr)
                
            if action_result.error:
                return f"Error: Extraction failed: {action_result.error}"
            return 'Error: No content could be extracted or scraped.'
            
        except Exception as e:
            # Try fallback on general exception as well
            try:
                page = await self.browser_session.get_current_page()
                fallback_text = await page.evaluate("() => document.body.innerText")
                if fallback_text and fallback_text.strip():
                    return f"[Extraction LLM errored, using page text fallback]:\n{fallback_text}"
            except Exception:
                pass
            return f"Error: Extraction failed with exception: {e}"

    BrowserUseServer._extract_content = _patched_extract_content

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
    # print("Bridge: BrowserUseServer patched with CDP and evaluate tool", file=sys.stderr)

# ---------------------------------------------------------------------------
# Frame Streaming Task
# ---------------------------------------------------------------------------

async def stream_browser_frames(browser_session, user_id: str, backend_url: str):
    import httpx
    import base64
    import asyncio
    import sys
    
    print(f"Bridge [stream]: Starting frame streaming for user_id={user_id} pointing to {backend_url}", file=sys.stderr)
    # Wait for the browser session to be ready
    await asyncio.sleep(2)
    
    last_frame = None
    sleep_duration = 0.35
    async with httpx.AsyncClient(timeout=5.0) as client:
        while True:
            # Check if browser session is alive
            if getattr(browser_session, "_is_killed", False):
                print("Bridge [stream]: Browser session is killed, stopping stream loop.", file=sys.stderr)
                break
            try:
                if sleep_duration > 0.5:
                    # Rest Mode: skip taking screenshots to save CPU/memory resources.
                    # Periodically check with the backend if we should resume active streaming.
                    url = f"{backend_url.rstrip('/')}/sciparser/v1/browser/frame/{user_id}"
                    resp = await client.post(url, json={"check_only": True})
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("is_active", False):
                            print("Bridge [stream]: Resume active frame streaming.", file=sys.stderr)
                            sleep_duration = 0.35  # Resume 3 FPS
                        else:
                            sleep_duration = 2.0   # Stay in Rest Mode (poll every 2.0s)
                else:
                    # Active Mode: capture screenshot and POST it
                    screenshot_bytes = await browser_session.take_screenshot(format='jpeg', quality=65)
                    if screenshot_bytes:
                        b64_frame = base64.b64encode(screenshot_bytes).decode('utf-8')
                        
                        if b64_frame != last_frame:
                            last_frame = b64_frame
                            url = f"{backend_url.rstrip('/')}/sciparser/v1/browser/frame/{user_id}"
                            resp = await client.post(url, json={"frame": b64_frame})
                            if resp.status_code == 200:
                                data = resp.json()
                                if not data.get("is_active", False):
                                    print("Bridge [stream]: Entering rest mode (no active task running).", file=sys.stderr)
                                    sleep_duration = 2.0  # Switch to Rest Mode
                            else:
                                print(f"Bridge [stream]: POST frame failed with status {resp.status_code}", file=sys.stderr)
            except Exception as e:
                print(f"Bridge [stream] error: {e}", file=sys.stderr)
            await asyncio.sleep(sleep_duration)

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
    
    # Start live screenshot streaming task
    user_id = os.getenv("BROWSER_USE_USER_ID", "system")
    backend_url = os.getenv("BACKEND_API_URL", "http://localhost:8000")
    # Store reference to prevent garbage collection
    _stream_task = asyncio.create_task(stream_browser_frames(browser_session, user_id, backend_url))
    
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