import os
import sys
import json
import time
import asyncio
import socket
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src import config

# ---------------------------------------------------------------------------
# Stealth JS injected into every page before any content loads
# ---------------------------------------------------------------------------

STEALTH_JS = """
(function() {
    // 1. Hide webdriver flag
    try {
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
            configurable: true,
        });
    } catch(e) {}

    // 2. Remove CDP / Playwright runtime artifacts
    try { delete window.__playwright; } catch(e) {}
    try { delete window.__pwInitScripts; } catch(e) {}
    try { delete window.__PWDEBUGGER__; } catch(e) {}
    try {
        Object.getOwnPropertyNames(window).forEach(function(key) {
            if (key.startsWith('cdc_')) { try { delete window[key]; } catch(e) {} }
        });
    } catch(e) {}

    // 3. Spoof navigator.plugins with realistic entries
    try {
        const mimeProto = Object.create(MimeType.prototype);
        function makeMime(type, desc, suffixes) {
            const m = Object.create(mimeProto);
            Object.defineProperties(m, {
                type:        { value: type,     enumerable: true },
                description: { value: desc,     enumerable: true },
                suffixes:    { value: suffixes, enumerable: true },
            });
            return m;
        }
        function makePlugin(name, desc, filename, mimes) {
            const p = Object.create(Plugin.prototype);
            Object.defineProperties(p, {
                name:        { value: name,         enumerable: true },
                description: { value: desc,         enumerable: true },
                filename:    { value: filename,      enumerable: true },
                length:      { value: mimes.length,  enumerable: true },
            });
            mimes.forEach(function(m, i) { p[i] = m; p[m.type] = m; });
            return p;
        }
        const pdfMime = makeMime('application/pdf', 'Portable Document Format', 'pdf');
        const pdfPlugin = makePlugin('PDF Viewer', 'Portable Document Format', 'internal-pdf-viewer', [pdfMime]);
        const chromePdf = makePlugin('Chrome PDF Viewer', 'Portable Document Format', 'internal-pdf-viewer', [pdfMime]);
        const nativeClient = makePlugin('Native Client', '', 'internal-nacl-plugin', []);
        const arr = Object.create(PluginArray.prototype);
        [pdfPlugin, chromePdf, nativeClient].forEach(function(p, i) { arr[i] = p; arr[p.name] = p; });
        Object.defineProperties(arr, {
            length:    { value: 3 },
            item:      { value: function(i) { return arr[i] || null; } },
            namedItem: { value: function(n) { return arr[n] || null; } },
            refresh:   { value: function() {} },
        });
        Object.defineProperty(navigator, 'plugins', { get: function() { return arr; }, configurable: true });
    } catch(e) {}

    // 4. Spoof navigator.languages
    try {
        Object.defineProperty(navigator, 'languages', {
            get: function() { return ['en-US', 'en']; },
            configurable: true,
        });
    } catch(e) {}

    // 5. Canvas fingerprint: add per-session noise to both toDataURL and getImageData
    try {
        // _noiseByte is in range [1, 15] — always non-zero, subtle enough to
        // not break visual rendering but distinct enough to shift fingerprints.
        const _noiseByte = (Math.floor(Math.random() * 15) + 1) & 0xff;

        // Patch toDataURL
        const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
        HTMLCanvasElement.prototype.toDataURL = function(type) {
            var ctx2d = this.getContext('2d');
            if (ctx2d && this.width > 0 && this.height > 0) {
                try {
                    var id = ctx2d.getImageData(0, 0, 1, 1);
                    id.data[0] = (id.data[0] ^ _noiseByte) & 0xff;
                    ctx2d.putImageData(id, 0, 0);
                } catch(e2) {}
            }
            return origToDataURL.apply(this, arguments);
        };

        // Patch CanvasRenderingContext2D.prototype.getImageData
        const origGetCtx = HTMLCanvasElement.prototype.getContext;
        HTMLCanvasElement.prototype.getContext = function(contextType) {
            var ctx = origGetCtx.apply(this, arguments);
            if (ctx && (contextType === '2d') && !ctx._stealthPatched) {
                ctx._stealthPatched = true;
                var origGetImageData = ctx.getImageData.bind(ctx);
                ctx.getImageData = function(sx, sy, sw, sh) {
                    var imageData = origGetImageData(sx, sy, sw, sh);
                    if (imageData && imageData.data && imageData.data.length > 0) {
                        imageData.data[0] = (imageData.data[0] ^ _noiseByte) & 0xff;
                    }
                    return imageData;
                };
            }
            return ctx;
        };
    } catch(e) {}

    // 6. WebGL RENDERER / VENDOR spoofing
    try {
        const _RENDERER = 'ANGLE (NVIDIA, NVIDIA GeForce GTX 1650 Direct3D11 vs_5_0 ps_5_0, D3D11)';
        const _VENDOR   = 'Google Inc. (NVIDIA)';
        function patchWGL(proto) {
            var orig = proto.getParameter;
            proto.getParameter = function(param) {
                if (param === 37446) return _RENDERER;  // UNMASKED_RENDERER_WEBGL
                if (param === 37445) return _VENDOR;    // UNMASKED_VENDOR_WEBGL
                return orig.call(this, param);
            };
        }
        if (typeof WebGLRenderingContext  !== 'undefined') patchWGL(WebGLRenderingContext.prototype);
        if (typeof WebGL2RenderingContext !== 'undefined') patchWGL(WebGL2RenderingContext.prototype);
    } catch(e) {}

    // 7. Ensure window.chrome.runtime exists (headless Chromium lacks it)
    try {
        if (!window.chrome) window.chrome = {};
        if (!window.chrome.runtime) {
            window.chrome.runtime = {
                connect:      function() { return {}; },
                sendMessage:  function() {},
                onMessage:    { addListener: function() {}, removeListener: function() {} },
                id:           undefined,
            };
        }
    } catch(e) {}

    // 8. Notification.permission → 'default' (headless reports 'denied')
    try {
        Object.defineProperty(Notification, 'permission', {
            get: function() { return 'default'; },
            configurable: true,
        });
    } catch(e) {}

    // 9. Screen / window dimensions consistent with 1920×1080
    try {
        Object.defineProperty(screen, 'width',       { get: function() { return 1920; }, configurable: true });
        Object.defineProperty(screen, 'height',      { get: function() { return 1080; }, configurable: true });
        Object.defineProperty(screen, 'availWidth',  { get: function() { return 1920; }, configurable: true });
        Object.defineProperty(screen, 'availHeight', { get: function() { return 1040; }, configurable: true });
        Object.defineProperty(window, 'outerWidth',  { get: function() { return 1920; }, configurable: true });
        Object.defineProperty(window, 'outerHeight', { get: function() { return 1080; }, configurable: true });
    } catch(e) {}
})();
"""

# ---------------------------------------------------------------------------
async def _patch_session_stealth(session: object) -> None:
    """
    After BrowserSession.start(), inject STEALTH_JS as an init script on the
    browser context so it runs before any page content loads on every new page.
    """
    try:
        ctx = (
            getattr(session, "context", None)
            or getattr(session, "browser_context", None)
            or getattr(session, "_context", None)
        )
        if ctx is None:
            print("Bridge: stealth — no context found on session", file=sys.stderr)
            return
        add_init = getattr(ctx, "add_init_script", None)
        if callable(add_init):
            await add_init(STEALTH_JS)
            print("Bridge: stealth init script injected on browser context", file=sys.stderr)
        else:
            print("Bridge: stealth — context.add_init_script not available", file=sys.stderr)
    except Exception as exc:
        print(f"Bridge: _patch_session_stealth failed: {exc}", file=sys.stderr)

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


async def _wait_for_cdp(port: int, timeout_secs: int = None) -> bool:
    """Poll http://<host>:PORT/json/version until Chrome answers."""
    import aiohttp
    timeout_secs = timeout_secs if timeout_secs is not None else int(config.BROWSER_CDP_READY_TIMEOUT_SECONDS)
    url = f"http://{config.BROWSER_DEFAULT_CDP_HOST}:{port}/json/version"
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

# ---------------------------------------------------------------------------
# User-agent rotation pool
# ---------------------------------------------------------------------------

_USER_AGENTS = [
    # Chrome on Windows (index 0 — default)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    # Chrome on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    # Chrome on Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]

def _pick_user_agent() -> str:
    """Return a user agent string selected by the BROWSER_USER_AGENT_INDEX env var."""
    try:
        idx = int(os.getenv("BROWSER_USER_AGENT_INDEX", str(config.BROWSER_USER_AGENT_INDEX_DEFAULT)))
    except (ValueError, TypeError):
        idx = config.BROWSER_USER_AGENT_INDEX_DEFAULT
    return _USER_AGENTS[idx % len(_USER_AGENTS)]


async def _launch_chrome(port: int, user_data_dir: str, headless: bool, proxy_url: str = "") -> asyncio.subprocess.Process:
    args = [
        CHROME_BINARY,
        f"--remote-debugging-port={port}",
        "--remote-allow-origins=*",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-setuid-sandbox",
        "--no-first-run",
        "--no-default-browser-check",
        "--window-size=1920,1080",
        "--start-maximized",
        "--force-color-profile=srgb",
        "--disable-features=IsolateOrigins,site-per-process",
        "--password-store=basic",
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        "--disable-notifications",
        
        "--disable-popup-blocking",
        "--disable-default-apps",
        "--mute-audio",
        "--lang=en-US,en",
        # --- Network / proxy ---------------------------------------------------
        # Use user-supplied proxy if configured; otherwise bypass Replit's transparent proxy.
        f"--proxy-server={proxy_url}" if proxy_url else "--no-proxy-server",
        # Don't fail on self-signed or mismatched TLS certs
        "--ignore-certificate-errors",
        "--ignore-ssl-errors",
        "--ignore-certificate-errors-spki-list",
        "--allow-running-insecure-content",
        # Disable CORS enforcement (lets the agent access any origin)
        "--disable-web-security",
        "--allow-file-access-from-files",
        # Suppress harmless dBus / sandbox noise in headless Linux
        "--disable-dbus",
        "--disable-background-networking",
        "--disable-client-side-phishing-detection",
        "--disable-sync",
        "--metrics-recording-only",
        "--safebrowsing-disable-auto-update",
        f"--user-agent={_pick_user_agent()}",
        f"--user-data-dir={user_data_dir}",
    ]
    if headless:
        # In headless mode we must keep --disable-gpu (no display server)
        args.append("--headless=new")
        args.append("--disable-gpu")
    # In non-headless mode, omit --disable-gpu so WebGL looks realistic

    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    print(f"Bridge: Chrome launched — pid={proc.pid}  port={port}", file=sys.stderr)
    return proc


# ---------------------------------------------------------------------------
# Write browser-use config.json so _init_browser_session gets cdp_url
# ---------------------------------------------------------------------------

def _write_browser_use_config(cdp_url: str, headless: bool) -> None:
    """
    Write the browser-use config.json with cdp_url so that
    BrowserUseServer.__init__ → load_browser_use_config() picks it up
    and passes it to BrowserProfile(cdp_url=...) inside _init_browser_session.

    Uses browser-use's own Config._get_config_path() so the file lands at the
    exact path the library will read from (respects XDG_CONFIG_HOME,
    BROWSER_USE_CONFIG_DIR, and BROWSER_USE_CONFIG_PATH env vars).
    """
    try:
        from browser_use.config import Config as _BUConfig
        config_path = _BUConfig()._get_config_path()
    except Exception:
        # Fallback: respect XDG_CONFIG_HOME if set, else ~/.config
        xdg = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
        config_path = Path(xdg) / "browseruse" / "config.json"
    config_dir = config_path.parent
    config_dir.mkdir(parents=True, exist_ok=True)
    config_data = {
        "browser_profile": {
            "bridge-default": {
                "id": "bridge-default",
                "default": True,
                "headless": headless,
                "cdp_url": cdp_url,
            }
        },
        "llm": {},
        "agent": {},
    }
    config_path.write_text(json.dumps(config_data, indent=2))
    print(f"Bridge: wrote browser-use config → {config_path}  cdp_url={cdp_url}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Monkey-patch: wait for Chrome + reset browser_session on failure
# ---------------------------------------------------------------------------

def _patch_mcp_server_session_retry(chrome_ready: asyncio.Event, cdp_url: str, headless: bool, proxy_url: str = "") -> None:
    """
    Full replacement of BrowserUseServer._init_browser_session that:

    1. Waits for chrome_ready before attempting to connect.
    2. Creates BrowserSession(cdp_url=..., is_local=False) directly — bypassing
       the config chain and the BrowserSession.__init__ logic that forces
       is_local=True whenever the cdp_url kwarg is None.
    3. Resets self.browser_session = None on any failure so the next tool call
       creates a fresh session (prevents permanent _cdp_client_root=None).
    """
    try:
        from browser_use.mcp.server import BrowserUseServer
        from browser_use.browser import BrowserSession
    except ImportError as e:
        print(f"Bridge: import error — skipping patch: {e}", file=sys.stderr)
        return

    if not hasattr(BrowserUseServer, "_init_browser_session"):
        print("Bridge: _init_browser_session not found — skipping patch", file=sys.stderr)
        return

    # Capture cdp_url, headless, and proxy_url in closure
    _cdp_url = cdp_url
    _headless = headless
    _proxy_url = proxy_url

    async def _patched_init(self, allowed_domains: "list[str] | None" = None, **kwargs):
        # Already connected
        if self.browser_session:
            return

        # Wait until our Chrome is confirmed ready
        if not chrome_ready.is_set():
            print(f"Bridge [patch]: waiting for Chrome at {_cdp_url}...", file=sys.stderr)
            try:
                await asyncio.wait_for(chrome_ready.wait(), timeout=config.BROWSER_CDP_READY_TIMEOUT_SECONDS)
                print("Bridge [patch]: Chrome ready — connecting", file=sys.stderr)
            except asyncio.TimeoutError:
                print(f"Bridge [patch]: {config.BROWSER_CDP_READY_TIMEOUT_SECONDS}s timeout waiting for Chrome — trying anyway", file=sys.stderr)

        print(f"Bridge [patch]: creating BrowserSession(cdp_url={_cdp_url}, is_local=False)", file=sys.stderr)

        try:
            # Create session with explicit cdp_url + is_local=False.
            # Passing cdp_url as a kwarg prevents BrowserSession.__init__ line-375
            # from overriding is_local=True, which would cause start() to dispatch
            # BrowserLaunchEvent and invoke LocalBrowserWatchdog.
            session = BrowserSession(
                cdp_url=_cdp_url,
                is_local=False,
                headless=_headless,
                keep_alive=True,
                disable_security=True,
                allowed_domains=allowed_domains or None,
                **({"proxy": {"server": _proxy_url}} if _proxy_url else {}),
            )
            self.browser_session = session
            await session.start()
            print("Bridge [patch]: BrowserSession started successfully", file=sys.stderr)

            # Inject stealth JS on the browser context so every page gets it
            # before any content loads (must be done before any navigation).
            await _patch_session_stealth(session)

            # Track session for management (same as original)
            if hasattr(self, '_track_session'):
                self._track_session(session)

        except Exception as exc:
            self.browser_session = None
            print(
                f"Bridge [patch]: BrowserSession start failed ({exc!r}) — "
                "reset browser_session=None for retry",
                file=sys.stderr,
            )
            raise

    BrowserUseServer._init_browser_session = _patched_init  # type: ignore[method-assign]
    print("Bridge: _init_browser_session patched (direct CDP connect, no LocalBrowserWatchdog)", file=sys.stderr)


# ---------------------------------------------------------------------------
# Patch: add human-like interaction tools
# (browser_key_press, browser_hover, browser_wait, browser_drag)
# ---------------------------------------------------------------------------

def _patch_add_human_tools() -> None:
    """
    Extend the browser-use MCP server with four missing human-interaction tools:
      browser_key_press  — keyboard key / combo (Enter, Tab, ArrowDown, …)
      browser_hover      — move mouse to element or coords without clicking
      browser_wait       — sleep N milliseconds (wait for autocomplete / animations)
      browser_drag       — click-drag from one position to another

    Strategy
    --------
    1.  Monkey-patch BrowserUseServer._execute_tool so the new tool names are routed
        to our implementations.
    2.  Monkey-patch BrowserUseServer._setup_handlers so that after the original
        handler runs we replace the MCP Server's ListToolsRequest handler with one
        that appends the new tool schemas — that way langchain_mcp_adapters picks
        them up when it calls list_tools().
    """
    try:
        from browser_use.mcp.server import BrowserUseServer
        import mcp.types as mcp_types
    except ImportError as e:
        print(f"Bridge: import error — skipping human-tools patch: {e}", file=sys.stderr)
        return

    # ── Tool schema definitions ────────────────────────────────────────────
    NEW_TOOL_SCHEMAS = [
        mcp_types.Tool(
            name="browser_key_press",
            description=(
                "Press a keyboard key or combination on the currently focused element. "
                "Use this to: submit forms (Enter), move between fields (Tab), "
                "close dialogs (Escape), navigate autocomplete dropdowns (ArrowDown/ArrowUp). "
                "Always call this after browser_type or after clicking an autocomplete suggestion "
                "to make sure the form is actually submitted. "
                "Examples: 'Enter', 'Tab', 'Escape', 'ArrowDown', 'ArrowUp', "
                "'Control+A', 'Control+C', 'Backspace', 'Delete'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": (
                            "Key name. Single: Enter, Tab, Escape, Backspace, Delete, Space, "
                            "ArrowDown, ArrowUp, ArrowLeft, ArrowRight, Home, End, PageDown, PageUp. "
                            "Combinations: Control+A, Control+C, Control+V, Shift+Enter, Shift+Tab."
                        ),
                    }
                },
                "required": ["key"],
            },
        ),
        mcp_types.Tool(
            name="browser_wait",
            description=(
                "Pause execution for a specified number of milliseconds. "
                "Use after browser_type to let autocomplete suggestions load (300–800 ms), "
                "or after a click to wait for animations/page transitions (500–1500 ms)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "milliseconds": {
                        "type": "integer",
                        "description": "Milliseconds to wait. Range 50–8000. Typical: 500 (animation), 800 (autocomplete).",
                        "default": 500,
                    }
                },
            },
        ),
    ]

    # ── Tool implementations ───────────────────────────────────────────────

    async def _exec_key_press(srv, args: dict) -> str:
        if not srv.browser_session:
            return "Error: No browser session active"
        key = str(args.get("key", "Enter"))
        try:
            page = await srv.browser_session.get_current_page()
            if page is None:
                return "Error: No active page"
            await page.press(key)
            return f"Pressed key: {key}"
        except Exception as exc:
            return f"Error pressing key '{key}': {exc}"

    async def _exec_wait(srv, args: dict) -> str:
        ms = max(50, min(8000, int(args.get("milliseconds", 500))))
        await asyncio.sleep(ms / 1000.0)
        return f"Waited {ms} ms"

    # ── Patch 1: _execute_tool routing ────────────────────────────────────
    _orig_execute = BrowserUseServer._execute_tool

    async def _patched_execute_tool(self, tool_name: str, arguments: dict):
        # ── Standard (Chrome CDP) path ─────────────────────────────────────
        if tool_name == "browser_key_press":
            return await _exec_key_press(self, arguments)
        if tool_name == "browser_wait":
            return await _exec_wait(self, arguments)
        return await _orig_execute(self, tool_name, arguments)

    BrowserUseServer._execute_tool = _patched_execute_tool  # type: ignore[method-assign]

    # ── Patch 2: _setup_handlers — extend list_tools response ────────────
    _orig_setup = BrowserUseServer._setup_handlers

    def _patched_setup_handlers(self):
        _orig_setup(self)
        # The MCP Server stores handlers in self.server.request_handlers keyed by
        # the request type class.  We replace the ListToolsRequest handler with a
        # wrapper that appends our new schemas to whatever the original returned.
        try:
            ListToolsRequest = mcp_types.ListToolsRequest
            ListToolsResult  = mcp_types.ListToolsResult
            orig_lt = self.server.request_handlers.get(ListToolsRequest)
            if orig_lt is None:
                return

            async def _extended_list_tools(req):
                result = await orig_lt(req)
                if isinstance(result, ListToolsResult):
                    result.tools = list(result.tools) + NEW_TOOL_SCHEMAS
                return result

            self.server.request_handlers[ListToolsRequest] = _extended_list_tools
        except Exception as exc:
            print(f"Bridge: list_tools extend failed: {exc}", file=sys.stderr)

    BrowserUseServer._setup_handlers = _patched_setup_handlers  # type: ignore[method-assign]
    print(
        "Bridge: human-tools patched — browser_key_press, browser_wait",
        file=sys.stderr,
    )


# ---------------------------------------------------------------------------
# Main bridge coroutine
# ---------------------------------------------------------------------------

async def run_bridge():
    from browser_use.mcp.server import main
    import inspect

    # -- Read per-session runtime overrides injected by MCPToolManager --------
    # These come from config.py's browser_*_override() accessors: this bridge
    # runs as a dedicated subprocess per user session, so each one only ever
    # sees its own copy of these env vars (never other sessions' values).
    cdp_url_env    = config.browser_cdp_url_override()
    own_browser    = config.browser_use_own_browser()
    port_env       = config.browser_cdp_port_override()
    port           = int(port_env) if port_env and port_env not in ("", "0") else find_free_port()
    headless       = os.getenv("BROWSER_USE_HEADLESS", str(config.BROWSER_USE_HEADLESS_DEFAULT)).lower() != "false"
    browser_engine = os.getenv("BROWSER_ENGINE", config.BROWSER_ENGINE).lower()
    proxy_url      = config.browser_proxy_url_override()

    # Persistent profile directory — cookies, localStorage, and history
    # survive between runs so the browser looks like a real returning user.
    _default_profile = str(Path.home() / ".config" / "browser-use" / "profile")
    user_data_dir = config.browser_user_data_dir_override(_default_profile)
    os.makedirs(user_data_dir, exist_ok=True)

    cdp_url = cdp_url_env or f"http://{config.BROWSER_DEFAULT_CDP_HOST}:{port}"

    print(
        f"Bridge: port={port}  headless={headless}  own_browser={own_browser}  "
        f"cdp_url={cdp_url}  user_data_dir={user_data_dir}  proxy={'<set>' if proxy_url else 'none'}",
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
                chrome_proc = await _launch_chrome(port, user_data_dir, headless, proxy_url=proxy_url)

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

    # -- Write browser-use config so _init_browser_session uses our cdp_url ---
    # Must happen BEFORE main() calls BrowserUseServer.__init__, which reads
    # the config file once via load_browser_use_config().
    _write_browser_use_config(cdp_url, headless)

    # -- Apply patches --------------------------------------------------------
    _patch_mcp_server_session_retry(chrome_ready, cdp_url, headless, proxy_url=proxy_url)
    _patch_add_human_tools()  # adds browser_key_press / browser_hover / browser_wait / browser_drag

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
