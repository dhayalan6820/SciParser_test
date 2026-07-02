import os
import sys
import json
import time
import asyncio
import socket
import tempfile
from pathlib import Path

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
# Camoufox Firefox automation state
# (set in run_bridge when BROWSER_ENGINE=camoufox)
# ---------------------------------------------------------------------------

_CAMOUFOX_WS_URL: str = ""
_CAMOUFOX_CONTEXT: object = None   # Playwright BrowserContext
_CAMOUFOX_PAGES: list = []         # Open Playwright Pages (tabs)
_CAMOUFOX_ACTIVE_IDX: int = 0      # Index of current page in _CAMOUFOX_PAGES
_CAMOUFOX_ELEMENTS: dict = {}      # index → element info from last get_state


class _CamoufoxSessionStub:
    """Minimal stub — passes BrowserUseServer's 'if self.browser_session:' checks.
    All actual browser operations are intercepted in _patched_execute_tool and
    routed to the live Playwright Firefox context so BrowserSession (Chrome/CDP)
    is never used."""
    id: str = "camoufox-firefox"

    async def stop(self, force: bool = False) -> None:
        pass


def _camoufox_page():
    """Return the currently active camoufox Playwright page (or None)."""
    if not _CAMOUFOX_PAGES:
        return None
    idx = min(_CAMOUFOX_ACTIVE_IDX, len(_CAMOUFOX_PAGES) - 1)
    return _CAMOUFOX_PAGES[idx]


# JS injected into every get_state call to extract visible interactive elements.
_CAMOUFOX_DOM_JS = r"""
() => {
    const results = [];
    const sel = 'a,button,input,select,textarea,[onclick],[role="button"],[role="link"],[tabindex]';
    const seen = new Set();
    let i = 0;
    document.querySelectorAll(sel).forEach(el => {
        if (seen.has(el)) return; seen.add(el);
        const r = el.getBoundingClientRect();
        if (r.width <= 0 || r.height <= 0) return;
        const st = window.getComputedStyle(el);
        if (st.display === 'none' || st.visibility === 'hidden' || parseFloat(st.opacity) < 0.05) return;
        results.push({
            index: i++,
            tag: el.tagName.toLowerCase(),
            text: (el.innerText || el.value || el.getAttribute('placeholder') || el.getAttribute('aria-label') || '').trim().slice(0, 80),
            type: el.type || null,
            href: el.href || null,
            cx: Math.round(r.left + r.width / 2),
            cy: Math.round(r.top + r.height / 2),
        });
    });
    return { url: location.href, title: document.title, elements: results };
}
"""


async def _ff_navigate(args: dict) -> str:
    global _CAMOUFOX_CONTEXT, _CAMOUFOX_PAGES, _CAMOUFOX_ACTIVE_IDX
    page = _camoufox_page()
    url = args.get("url", "")
    new_tab = args.get("new_tab", False)
    if new_tab and _CAMOUFOX_CONTEXT:
        try:
            new_page = await _CAMOUFOX_CONTEXT.new_page()
            await _CAMOUFOX_CONTEXT.add_init_script(STEALTH_JS)
            _CAMOUFOX_PAGES.append(new_page)
            _CAMOUFOX_ACTIVE_IDX = len(_CAMOUFOX_PAGES) - 1
            page = new_page
        except Exception:
            pass
    if not page:
        return "Error: No active camoufox page"
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        return f"Navigated to {page.url}"
    except Exception as exc:
        return f"Navigation error: {exc}"


async def _ff_click(args: dict) -> str:
    global _CAMOUFOX_ELEMENTS
    page = _camoufox_page()
    if not page:
        return "Error: No active camoufox page"
    cx = args.get("coordinate_x")
    cy = args.get("coordinate_y")
    idx = args.get("index")
    try:
        if cx is not None and cy is not None:
            await page.mouse.click(int(cx), int(cy))
            _write_mouse_state(float(cx), float(cy), "click")
            return f"Clicked at ({cx}, {cy})"
        if idx is not None:
            idx = int(idx)
            el = _CAMOUFOX_ELEMENTS.get(idx)
            if el:
                await page.mouse.click(el["cx"], el["cy"])
                _write_mouse_state(float(el["cx"]), float(el["cy"]), "click")
                return f"Clicked [{idx}] <{el.get('tag','?')}> {el.get('text','')[:40]}"
            return f"Error: element index {idx} not found — call browser_get_state first"
        return "Error: provide index or coordinate_x+coordinate_y"
    except Exception as exc:
        return f"Click error: {exc}"


async def _ff_type(args: dict) -> str:
    global _CAMOUFOX_ELEMENTS
    page = _camoufox_page()
    if not page:
        return "Error: No active camoufox page"
    idx = args.get("index")
    text = str(args.get("text", ""))
    try:
        if idx is not None:
            el = _CAMOUFOX_ELEMENTS.get(int(idx))
            if el:
                await page.mouse.click(el["cx"], el["cy"])
                _write_mouse_state(float(el["cx"]), float(el["cy"]), "click")
                await asyncio.sleep(0.1)
        await page.keyboard.type(text, delay=30)
        return f"Typed: {text[:60]}"
    except Exception as exc:
        return f"Type error: {exc}"


async def _ff_get_state(args: dict):
    import base64
    import mcp.types as mcp_types
    global _CAMOUFOX_ELEMENTS
    page = _camoufox_page()
    if not page:
        return [mcp_types.TextContent(type="text", text="Error: No active camoufox page")]
    try:
        dom = await page.evaluate(_CAMOUFOX_DOM_JS)
        _CAMOUFOX_ELEMENTS = {el["index"]: el for el in dom.get("elements", [])}
        lines = [
            f"URL: {dom.get('url', page.url)}",
            f"Title: {dom.get('title', '')}",
            f"Engine: Firefox (camoufox)",
            "",
            "Interactive elements — use [index] with browser_click / browser_type:",
        ]
        for el in dom.get("elements", []):
            typ = f"[{el['type']}]" if el.get("type") else ""
            href = f" → {el['href'][:50]}" if el.get("href") else ""
            lines.append(f"  [{el['index']}] <{el['tag']}>{typ} {el.get('text','')[:60]}{href}")
        content = [mcp_types.TextContent(type="text", text="\n".join(lines))]
        if args.get("include_screenshot"):
            try:
                ss = await page.screenshot(type="png")
                content.append(mcp_types.ImageContent(
                    type="image",
                    data=base64.b64encode(ss).decode(),
                    mimeType="image/png",
                ))
            except Exception:
                pass
        return content
    except Exception as exc:
        return [mcp_types.TextContent(type="text", text=f"State error: {exc}")]


async def _ff_screenshot(args: dict):
    import base64
    import mcp.types as mcp_types
    page = _camoufox_page()
    if not page:
        return [mcp_types.TextContent(type="text", text="Error: No active camoufox page")]
    try:
        ss = await page.screenshot(full_page=args.get("full_page", False), type="png")
        try:
            title = await page.title()
        except Exception:
            title = ""
        meta = json.dumps({"url": page.url, "title": title})
        return [
            mcp_types.TextContent(type="text", text=meta),
            mcp_types.ImageContent(
                type="image",
                data=base64.b64encode(ss).decode(),
                mimeType="image/png",
            ),
        ]
    except Exception as exc:
        return [mcp_types.TextContent(type="text", text=f"Screenshot error: {exc}")]


async def _ff_scroll(args: dict) -> str:
    page = _camoufox_page()
    if not page:
        return "Error: No active camoufox page"
    direction = args.get("direction", "down")
    delta = 400
    cx = args.get("coordinate_x")
    cy = args.get("coordinate_y")
    try:
        if cx is not None and cy is not None:
            await page.mouse.move(int(cx), int(cy))
            _write_mouse_state(float(cx), float(cy), "move")
        if direction == "down":
            await page.mouse.wheel(0, delta)
        elif direction == "up":
            await page.mouse.wheel(0, -delta)
        elif direction == "right":
            await page.mouse.wheel(delta, 0)
        elif direction == "left":
            await page.mouse.wheel(-delta, 0)
        return f"Scrolled {direction}"
    except Exception as exc:
        return f"Scroll error: {exc}"


async def _ff_go_back(_args: dict) -> str:
    page = _camoufox_page()
    if not page:
        return "Error: No active camoufox page"
    try:
        await page.go_back()
        return f"Went back to {page.url}"
    except Exception as exc:
        return f"Go back error: {exc}"


async def _ff_get_html(args: dict) -> str:
    page = _camoufox_page()
    if not page:
        return "Error: No active camoufox page"
    selector = args.get("selector")
    try:
        if selector:
            el = await page.query_selector(selector)
            return (await el.inner_html()) if el else f"No element: {selector}"
        return await page.content()
    except Exception as exc:
        return f"HTML error: {exc}"


async def _ff_extract(args: dict) -> str:
    page = _camoufox_page()
    if not page:
        return "Error: No active camoufox page"
    extract_links = args.get("extract_links", False)
    try:
        text = await page.evaluate("() => document.body.innerText")
        result = text[:5000]
        if extract_links:
            links = await page.evaluate(r"""
                () => [...document.querySelectorAll('a[href]')]
                    .map(a => (a.href + ' — ' + a.innerText.trim()).slice(0, 120))
                    .filter(s => s.length > 5).slice(0, 30)
            """)
            result += "\n\nLinks:\n" + "\n".join(links)
        return result
    except Exception as exc:
        return f"Extract error: {exc}"


async def _ff_list_tabs() -> str:
    if not _CAMOUFOX_PAGES:
        return "No open tabs"
    lines = []
    for i, p in enumerate(_CAMOUFOX_PAGES):
        try:
            t = await p.title()
            u = p.url
        except Exception:
            t, u = "?", "?"
        lines.append(f"[{i}] {t[:50]} — {u[:80]}")
    return "Tabs:\n" + "\n".join(lines)


async def _ff_switch_tab(args: dict) -> str:
    global _CAMOUFOX_ACTIVE_IDX
    try:
        idx = int(args.get("tab_id", 0))
        if 0 <= idx < len(_CAMOUFOX_PAGES):
            _CAMOUFOX_ACTIVE_IDX = idx
            try:
                await _CAMOUFOX_PAGES[idx].bring_to_front()
            except Exception:
                pass
            return f"Switched to tab {idx}: {_CAMOUFOX_PAGES[idx].url}"
        return f"Tab {idx} not found (have {len(_CAMOUFOX_PAGES)})"
    except Exception as exc:
        return f"Switch tab error: {exc}"


async def _ff_close_tab(args: dict) -> str:
    global _CAMOUFOX_ACTIVE_IDX, _CAMOUFOX_PAGES
    try:
        idx = int(args.get("tab_id", 0))
        if 0 <= idx < len(_CAMOUFOX_PAGES):
            await _CAMOUFOX_PAGES[idx].close()
            _CAMOUFOX_PAGES.pop(idx)
            _CAMOUFOX_ACTIVE_IDX = max(0, min(_CAMOUFOX_ACTIVE_IDX, len(_CAMOUFOX_PAGES) - 1))
            return f"Closed tab {idx}"
        return f"Tab {idx} not found"
    except Exception as exc:
        return f"Close tab error: {exc}"


async def _ff_key_press(args: dict) -> str:
    """Firefox-native keyboard press — uses Playwright page.keyboard.press()."""
    page = _camoufox_page()
    if not page:
        return "Error: No active camoufox page"
    key = str(args.get("key", "Enter"))
    try:
        await page.keyboard.press(key)
        return f"Pressed key: {key}"
    except Exception as exc:
        return f"Error pressing key '{key}': {exc}"


async def _ff_hover(args: dict) -> str:
    """Firefox-native hover — uses Playwright page.mouse.move()."""
    page = _camoufox_page()
    if not page:
        return "Error: No active camoufox page"
    cx = args.get("coordinate_x")
    cy = args.get("coordinate_y")
    idx = args.get("index")
    try:
        if cx is not None and cy is not None:
            await page.mouse.move(int(cx), int(cy))
            _write_mouse_state(float(cx), float(cy), "move")
            return f"Hovered at ({cx}, {cy})"
        if idx is not None:
            el = _CAMOUFOX_ELEMENTS.get(int(idx))
            if el:
                await page.mouse.move(el["cx"], el["cy"])
                _write_mouse_state(float(el["cx"]), float(el["cy"]), "move")
                return f"Hovered over element [{idx}] at ({el['cx']}, {el['cy']})"
            return f"Error: element {idx} not found — call browser_get_state first"
        return "Error: provide index or coordinate_x+coordinate_y"
    except Exception as exc:
        return f"Error hovering: {exc}"


async def _ff_drag(args: dict) -> str:
    """Firefox-native drag — uses Playwright mouse down/move/up sequence."""
    page = _camoufox_page()
    if not page:
        return "Error: No active camoufox page"
    try:
        fx, fy = int(args["from_x"]), int(args["from_y"])
        tx, ty = int(args["to_x"]),   int(args["to_y"])
        steps = max(5, min(50, int(args.get("steps", 15))))
        _write_mouse_state(float(fx), float(fy), "move")
        await page.mouse.move(fx, fy)
        await asyncio.sleep(0.08)
        await page.mouse.down()
        await asyncio.sleep(0.05)
        for i in range(1, steps + 1):
            ix = int(fx + (tx - fx) * i / steps)
            iy = int(fy + (ty - fy) * i / steps)
            _write_mouse_state(float(ix), float(iy), "move")
            await page.mouse.move(ix, iy)
            await asyncio.sleep(0.02)
        _write_mouse_state(float(tx), float(ty), "move")
        await page.mouse.up()
        return f"Dragged ({fx},{fy}) → ({tx},{ty}) in {steps} steps"
    except Exception as exc:
        return f"Error dragging: {exc}"

# ---------------------------------------------------------------------------
# Mouse-state temp file — shared with brain.py for cursor compositing
# ---------------------------------------------------------------------------

_MOUSE_STATE_PATH: str = ""  # set once in run_bridge() from CDP port
_last_mouse_xy: tuple = (0.0, 0.0)  # updated on every write for mouse.down() tracking


def _write_mouse_state(x: float, y: float, event: str, vp_w: int = 1280, vp_h: int = 800) -> None:
    """Write current mouse position to a temp file so brain.py can composite it."""
    global _last_mouse_xy
    _last_mouse_xy = (x, y)
    if not _MOUSE_STATE_PATH:
        return
    try:
        Path(_MOUSE_STATE_PATH).write_text(json.dumps({
            "x": x, "y": y, "event": event,
            "ts": time.time(), "vpW": vp_w, "vpH": vp_h,
        }))
    except Exception:
        pass


def _write_mouse_click_at_last_pos() -> None:
    """Write a 'click' event at the last known mouse position (used for mouse.down)."""
    x, y = _last_mouse_xy
    _write_mouse_state(x, y, "click")


def _apply_mouse_patch(mouse: object) -> None:
    """Monkey-patch move/click/down on a Playwright Mouse object for cursor tracking."""
    if getattr(mouse, "_cursor_patched", False):
        return
    orig_move  = mouse.move   # type: ignore[attr-defined]
    orig_click = mouse.click  # type: ignore[attr-defined]
    orig_down  = mouse.down   # type: ignore[attr-defined]

    async def _m_move(x: float, y: float, **kw):
        _write_mouse_state(float(x), float(y), "move")
        return await orig_move(x, y, **kw)

    async def _m_click(x: float, y: float, **kw):
        _write_mouse_state(float(x), float(y), "click")
        return await orig_click(x, y, **kw)

    async def _m_down(**kw):
        _write_mouse_click_at_last_pos()
        return await orig_down(**kw)

    mouse.move  = _m_move   # type: ignore[attr-defined]
    mouse.click = _m_click  # type: ignore[attr-defined]
    mouse.down  = _m_down   # type: ignore[attr-defined]
    mouse._cursor_patched = True  # type: ignore[attr-defined]
    print("Bridge: Playwright page.mouse patched for cursor tracking", file=sys.stderr)


async def _patch_page_mouse(page: object) -> None:
    """Extract mouse from a page (handles both property and async-method patterns)."""
    try:
        mouse = None
        # browser_use may wrap page.mouse as an async method
        raw_mouse = getattr(page, "mouse", None)
        if raw_mouse is not None:
            if callable(raw_mouse) and not hasattr(raw_mouse, "move"):
                # Looks like an async method — await it
                try:
                    mouse = await raw_mouse()
                except Exception:
                    mouse = None
            elif hasattr(raw_mouse, "move"):
                mouse = raw_mouse
        if mouse:
            _apply_mouse_patch(mouse)
    except Exception as exc:
        print(f"Bridge: _patch_page_mouse failed: {exc}", file=sys.stderr)


async def _patch_session_mouse(session: object) -> None:
    """
    After BrowserSession.start(), patch the active page's mouse and hook
    the browser context so future pages are patched automatically.
    """
    try:
        # Patch the current page
        get_page = getattr(session, "get_current_page", None)
        if callable(get_page):
            page = await get_page()
            if page:
                await _patch_page_mouse(page)

        # Hook context so every new page is also patched
        ctx = (
            getattr(session, "context", None)
            or getattr(session, "browser_context", None)
            or getattr(session, "_context", None)
        )
        if ctx and hasattr(ctx, "on"):
            def _on_new_page(pg):
                asyncio.create_task(_patch_page_mouse(pg))
            ctx.on("page", _on_new_page)
            print("Bridge: page-creation hook registered for cursor tracking", file=sys.stderr)
    except Exception as exc:
        print(f"Bridge: _patch_session_mouse failed: {exc}", file=sys.stderr)


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
        idx = int(os.getenv("BROWSER_USER_AGENT_INDEX", "0"))
    except (ValueError, TypeError):
        idx = 0
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
                await asyncio.wait_for(chrome_ready.wait(), timeout=90.0)
                print("Bridge [patch]: Chrome ready — connecting", file=sys.stderr)
            except asyncio.TimeoutError:
                print("Bridge [patch]: 90s timeout waiting for Chrome — trying anyway", file=sys.stderr)

        # ── Camoufox Firefox path ──────────────────────────────────────────────
        # When _CAMOUFOX_CONTEXT is set the Firefox context is already live.
        # Use a minimal stub so BrowserUseServer passes 'if self.browser_session:'
        # checks; all actual tool calls are intercepted in _patched_execute_tool
        # and routed to Playwright Firefox — BrowserSession (Chrome/CDP) is NOT
        # used. Chrome-specific flags and user-agent spoofing are also skipped
        # because _launch_chrome is never called in this path.
        if _CAMOUFOX_CONTEXT is not None:
            self.browser_session = _CamoufoxSessionStub()
            print(
                "Bridge [patch]: camoufox mode — using _CamoufoxSessionStub "
                f"(Firefox); {len(_CAMOUFOX_PAGES)} page(s) ready",
                file=sys.stderr,
            )
            return

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

            # Patch page.mouse so ALL Playwright mouse ops emit cursor events.
            # Await the initial page patch before returning so early tool calls
            # don't race ahead before the patch is applied; the context hook for
            # future pages is registered inside _patch_session_mouse.
            await _patch_session_mouse(session)

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
            name="browser_hover",
            description=(
                "Move the mouse cursor to an element or pixel coordinates WITHOUT clicking. "
                "Use to: reveal hover-only menus/tooltips, pre-position cursor before drag, "
                "or trigger CSS :hover effects that reveal a submit button."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "coordinate_x": {
                        "type": "integer",
                        "description": "X pixel coordinate (use with coordinate_y). Provide this OR index.",
                    },
                    "coordinate_y": {
                        "type": "integer",
                        "description": "Y pixel coordinate (use with coordinate_x).",
                    },
                    "index": {
                        "type": "integer",
                        "description": "Element index from browser_get_state. Provide this OR coordinate_x+coordinate_y.",
                    },
                },
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
        mcp_types.Tool(
            name="browser_drag",
            description=(
                "Click-and-drag from one set of pixel coordinates to another. "
                "Use for sliders, range inputs, drag-to-reorder lists, and drawing."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "from_x": {"type": "integer", "description": "Starting X coordinate."},
                    "from_y": {"type": "integer", "description": "Starting Y coordinate."},
                    "to_x": {"type": "integer", "description": "Ending X coordinate."},
                    "to_y": {"type": "integer", "description": "Ending Y coordinate."},
                    "steps": {
                        "type": "integer",
                        "description": "Number of intermediate mouse-move steps (smoother = more steps). Default 15.",
                        "default": 15,
                    },
                },
                "required": ["from_x", "from_y", "to_x", "to_y"],
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

    async def _exec_hover(srv, args: dict) -> str:
        if not srv.browser_session:
            return "Error: No browser session active"
        cx = args.get("coordinate_x")
        cy = args.get("coordinate_y")
        idx = args.get("index")
        try:
            page = await srv.browser_session.get_current_page()
            if page is None:
                return "Error: No active page"
            mouse = await page.mouse()

            if cx is not None and cy is not None:
                await mouse.move(int(cx), int(cy))
                _write_mouse_state(float(cx), float(cy), "move")
                return f"Hovered at ({cx}, {cy})"

            if idx is not None:
                element = await srv.browser_session.get_dom_element_by_index(idx)
                if not element:
                    return f"Error: Element {idx} not found"
                # Try common coordinate attributes on DOMElementNode
                coords = (
                    getattr(element, "viewport_coordinates", None)
                    or getattr(element, "center", None)
                )
                if coords is not None:
                    if hasattr(coords, "x"):
                        x, y = int(coords.x), int(coords.y)
                    elif hasattr(coords, "__iter__"):
                        x, y = int(coords[0]), int(coords[1])
                    else:
                        return f"Error: Cannot read coordinates for element {idx}"
                    await mouse.move(x, y)
                    _write_mouse_state(float(x), float(y), "move")
                    return f"Hovered over element {idx} at ({x}, {y})"
                return f"Error: Cannot determine coordinates for element {idx}"

            return "Error: Provide index or coordinate_x+coordinate_y"
        except Exception as exc:
            return f"Error hovering: {exc}"

    async def _exec_wait(srv, args: dict) -> str:
        ms = max(50, min(8000, int(args.get("milliseconds", 500))))
        await asyncio.sleep(ms / 1000.0)
        return f"Waited {ms} ms"

    async def _exec_drag(srv, args: dict) -> str:
        if not srv.browser_session:
            return "Error: No browser session active"
        fx, fy = int(args["from_x"]), int(args["from_y"])
        tx, ty = int(args["to_x"]),   int(args["to_y"])
        steps = max(5, min(50, int(args.get("steps", 15))))
        try:
            page = await srv.browser_session.get_current_page()
            if page is None:
                return "Error: No active page"
            mouse = await page.mouse()
            _write_mouse_state(float(fx), float(fy), "move")
            await mouse.move(fx, fy)
            await asyncio.sleep(0.08)
            await mouse.down()
            await asyncio.sleep(0.05)
            for i in range(1, steps + 1):
                ix = int(fx + (tx - fx) * i / steps)
                iy = int(fy + (ty - fy) * i / steps)
                _write_mouse_state(float(ix), float(iy), "move")
                await mouse.move(ix, iy)
                await asyncio.sleep(0.02)
            _write_mouse_state(float(tx), float(ty), "move")
            await mouse.up()
            return f"Dragged from ({fx}, {fy}) to ({tx}, {ty})"
        except Exception as exc:
            return f"Error dragging: {exc}"

    # ── Patch 1: _execute_tool routing ────────────────────────────────────
    _orig_execute = BrowserUseServer._execute_tool

    async def _patched_execute_tool(self, tool_name: str, arguments: dict):
        # ── Camoufox Firefox path ──────────────────────────────────────────
        # When _CAMOUFOX_CONTEXT is live, ALL browser_ tools are handled via
        # Playwright Firefox — BrowserSession (Chrome/CDP) is never invoked.
        if _CAMOUFOX_CONTEXT is not None and tool_name.startswith("browser_"):
            if tool_name == "browser_navigate":
                return await _ff_navigate(arguments)
            if tool_name == "browser_click":
                return await _ff_click(arguments)
            if tool_name == "browser_type":
                return await _ff_type(arguments)
            if tool_name == "browser_get_state":
                return await _ff_get_state(arguments)
            if tool_name == "browser_screenshot":
                return await _ff_screenshot(arguments)
            if tool_name == "browser_scroll":
                return await _ff_scroll(arguments)
            if tool_name == "browser_go_back":
                return await _ff_go_back(arguments)
            if tool_name == "browser_get_html":
                return await _ff_get_html(arguments)
            if tool_name == "browser_extract_content":
                return await _ff_extract(arguments)
            if tool_name == "browser_list_tabs":
                return await _ff_list_tabs()
            if tool_name == "browser_switch_tab":
                return await _ff_switch_tab(arguments)
            if tool_name == "browser_close_tab":
                return await _ff_close_tab(arguments)
            if tool_name == "browser_close":
                for p in list(_CAMOUFOX_PAGES):
                    try:
                        await p.close()
                    except Exception:
                        pass
                _CAMOUFOX_PAGES.clear()
                return "Browser closed"
            if tool_name == "browser_search_google":
                q = arguments.get("query", "")
                import urllib.parse
                return await _ff_navigate({"url": f"https://www.google.com/search?q={urllib.parse.quote(q)}"})
            # Custom tools: use Firefox-native implementations (no BrowserSession needed)
            if tool_name == "browser_key_press":
                return await _ff_key_press(arguments)
            if tool_name == "browser_hover":
                return await _ff_hover(arguments)
            if tool_name == "browser_wait":
                ms = max(50, min(8000, int(arguments.get("milliseconds", 500))))
                await asyncio.sleep(ms / 1000.0)
                return f"Waited {ms} ms"
            if tool_name == "browser_drag":
                return await _ff_drag(arguments)
            # Unknown browser_ tool — fall through to CDP path
        # ── Standard (Chrome CDP) path ─────────────────────────────────────
        if tool_name == "browser_key_press":
            return await _exec_key_press(self, arguments)
        if tool_name == "browser_hover":
            return await _exec_hover(self, arguments)
        if tool_name == "browser_wait":
            return await _exec_wait(self, arguments)
        if tool_name == "browser_drag":
            return await _exec_drag(self, arguments)
        # Intercept any browser_use native tool that carries pixel coordinates
        # so the cursor overlay tracks all agent click/interact operations.
        cx = arguments.get("coordinate_x") if arguments.get("coordinate_x") is not None else arguments.get("x")
        cy = arguments.get("coordinate_y") if arguments.get("coordinate_y") is not None else arguments.get("y")
        if cx is not None and cy is not None:
            is_click = any(k in tool_name for k in ("click", "input", "select", "type"))
            _write_mouse_state(float(cx), float(cy), "click" if is_click else "move")
        result = await _orig_execute(self, tool_name, arguments)
        # After any index-based action (click, type, scroll on element, etc.),
        # look up the element's bounding box and update the cursor position so the
        # overlay doesn't stay frozen during the majority of agent interactions.
        idx = arguments.get("index")
        if idx is not None and cx is None and cy is None:
            try:
                session = getattr(self, "browser_session", None)
                if session:
                    element = await session.get_dom_element_by_index(int(idx))
                    if element:
                        coords = (
                            getattr(element, "viewport_coordinates", None)
                            or getattr(element, "center", None)
                        )
                        if coords is not None:
                            if hasattr(coords, "x"):
                                ex, ey = float(coords.x), float(coords.y)
                            elif hasattr(coords, "__getitem__"):
                                ex, ey = float(coords[0]), float(coords[1])
                            else:
                                ex, ey = None, None
                            if ex is not None:
                                is_click = any(k in tool_name for k in ("click", "input", "select", "type"))
                                _write_mouse_state(ex, ey, "click" if is_click else "move")
            except Exception:
                pass
        return result

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
        "Bridge: human-tools patched — browser_key_press, browser_hover, browser_wait, browser_drag",
        file=sys.stderr,
    )


# ---------------------------------------------------------------------------
# Main bridge coroutine
# ---------------------------------------------------------------------------

async def run_bridge():
    from browser_use.mcp.server import main
    import inspect

    # -- Read env vars set by MCPToolManager ----------------------------------
    cdp_url_env    = os.getenv("MCP_BROWSER_CDP_URL") or os.getenv("BROWSER_CDP_URL")
    own_browser    = os.getenv("MCP_BROWSER_USE_OWN_BROWSER", "false").lower() == "true"
    port_env       = os.getenv("BROWSER_USE_CDP_PORT")
    port           = int(port_env) if port_env and port_env not in ("", "0") else find_free_port()
    headless       = os.getenv("BROWSER_USE_HEADLESS", "true").lower() != "false"
    browser_engine = os.getenv("BROWSER_ENGINE", "camoufox").lower()
    proxy_url      = os.getenv("BROWSER_PROXY_URL", "").strip()  # e.g. http://user:pass@host:port

    # Persistent profile directory — cookies, localStorage, and history
    # survive between runs so the browser looks like a real returning user.
    _default_profile = str(Path.home() / ".config" / "browser-use" / "profile")
    user_data_dir = os.getenv("BROWSER_USER_DATA_DIR", _default_profile)
    os.makedirs(user_data_dir, exist_ok=True)

    cdp_url = cdp_url_env or f"http://localhost:{port}"

    # Set the mouse-state file path so _write_mouse_state() can use it
    global _MOUSE_STATE_PATH
    _MOUSE_STATE_PATH = f"/tmp/agent_mouse_{port}.json"
    print(f"Bridge: mouse state file → {_MOUSE_STATE_PATH}", file=sys.stderr)

    print(
        f"Bridge: port={port}  headless={headless}  own_browser={own_browser}  "
        f"cdp_url={cdp_url}  user_data_dir={user_data_dir}  proxy={'<set>' if proxy_url else 'none'}",
        file=sys.stderr,
    )

    # -- Shared Event: set when Chrome is confirmed ready ---------------------
    chrome_ready = asyncio.Event()
    chrome_proc: asyncio.subprocess.Process | None = None

    if browser_engine == "camoufox":
        # -- Camoufox path (Option C) -----------------------------------------
        # Launch Firefox-based camoufox; it handles fingerprinting internally.
        # We extract its ws_endpoint and store it in _CAMOUFOX_WS_URL so
        # _patched_init can connect via BrowserSession(wss_url=...).
        global _CAMOUFOX_WS_URL
        try:
            import camoufox  # type: ignore[import]
            print("Bridge: camoufox engine selected", file=sys.stderr)

            async def _start_camoufox_background() -> None:
                global _CAMOUFOX_WS_URL, _CAMOUFOX_CONTEXT, _CAMOUFOX_PAGES
                nonlocal chrome_proc  # declared once at top to satisfy Python scoping rules
                try:
                    print("Bridge: launching camoufox (Firefox) browser...", file=sys.stderr)
                    # AsyncCamoufox is the correct async context manager — it wraps
                    # playwright.async_api.PlaywrightContextManager and calls
                    # AsyncNewBrowser(playwright, ...) internally, returning a
                    # Browser or BrowserContext.  AsyncNewBrowser itself is a plain
                    # async function that requires a Playwright object, not a CM.
                    async with camoufox.AsyncCamoufox(
                        headless=headless,
                        **({"proxy": {"server": proxy_url}} if proxy_url else {}),
                    ) as browser_or_ctx:
                        # AsyncCamoufox may yield a Browser or BrowserContext
                        # depending on whether persistent_context is set.
                        # Normalise to a BrowserContext and inject stealth script.
                        if hasattr(browser_or_ctx, "new_context"):
                            # It's a Playwright Browser — create/reuse a context
                            _br = browser_or_ctx
                            ws = getattr(_br, "ws_endpoint", None)
                            if ws:
                                _CAMOUFOX_WS_URL = ws
                                print(
                                    f"Bridge: camoufox ws_endpoint extracted — {ws}",
                                    file=sys.stderr,
                                )
                            else:
                                print(
                                    "Bridge: camoufox ws_endpoint not available "
                                    "(Firefox launched without remote-debugging — "
                                    "using direct Playwright context instead)",
                                    file=sys.stderr,
                                )
                            _ctx = _br.contexts[0] if _br.contexts else await _br.new_context()
                        else:
                            # It's already a BrowserContext (persistent_context=True path)
                            _ctx = browser_or_ctx
                            _br = getattr(_ctx, "browser", None)
                            if _br:
                                ws = getattr(_br, "ws_endpoint", None)
                                if ws:
                                    _CAMOUFOX_WS_URL = ws
                                    print(
                                        f"Bridge: camoufox ws_endpoint extracted from ctx.browser — {ws}",
                                        file=sys.stderr,
                                    )

                        _CAMOUFOX_CONTEXT = _ctx

                        # Inject stealth JS so every new page gets it at creation
                        await _ctx.add_init_script(STEALTH_JS)

                        # Seed the pages list
                        if _ctx.pages:
                            _CAMOUFOX_PAGES = list(_ctx.pages)
                        else:
                            _CAMOUFOX_PAGES = [await _ctx.new_page()]

                        print(
                            f"Bridge: camoufox Firefox ready — "
                            f"{len(_CAMOUFOX_PAGES)} page(s), "
                            f"ws_endpoint={_CAMOUFOX_WS_URL or 'N/A (direct Playwright context)'}, "
                            "Chrome-specific flags skipped (Firefox handles fingerprinting)",
                            file=sys.stderr,
                        )

                        # Signal init complete — no Chrome subprocess needed
                        chrome_ready.set()

                        # Keep the context manager alive until bridge exits
                        await asyncio.Event().wait()

                except Exception as exc:
                    print(f"Bridge: camoufox launch error — {exc!r}", file=sys.stderr)
                    # Camoufox failed — fall back to Chrome so the bridge still works
                    if own_browser and chrome_proc is None:
                        try:
                            print("Bridge: camoufox failed — falling back to Chrome", file=sys.stderr)
                            # Write a flag file so the backend can notify the user
                            try:
                                import json as _json
                                _flag_path = f"/tmp/camoufox_fallback_{port}.json"
                                Path(_flag_path).write_text(
                                    _json.dumps({"fallback": True, "reason": str(exc)})
                                )
                                print(f"Bridge: wrote camoufox fallback flag → {_flag_path}", file=sys.stderr)
                            except Exception as _fe:
                                print(f"Bridge: could not write fallback flag — {_fe!r}", file=sys.stderr)
                            chrome_proc = await _launch_chrome(port, user_data_dir, headless, proxy_url=proxy_url)
                            async def _drain_err():
                                assert chrome_proc.stderr
                                while True:
                                    line = await chrome_proc.stderr.readline()
                                    if not line:
                                        break
                            asyncio.create_task(_drain_err())
                            await _wait_for_cdp(port, timeout_secs=60)
                        except Exception as exc2:
                            print(f"Bridge: Chrome fallback also failed — {exc2!r}", file=sys.stderr)
                    chrome_ready.set()

            asyncio.create_task(_start_camoufox_background())
        except ImportError:
            print("Bridge: camoufox not installed — falling back to Chrome", file=sys.stderr)
            # Write a flag file so the backend can notify the user about the fallback
            try:
                import json as _json
                _flag_path = f"/tmp/camoufox_fallback_{port}.json"
                Path(_flag_path).write_text(
                    _json.dumps({"fallback": True, "reason": "camoufox not installed"})
                )
                print(f"Bridge: wrote camoufox fallback flag → {_flag_path}", file=sys.stderr)
            except Exception as _fe:
                print(f"Bridge: could not write fallback flag — {_fe!r}", file=sys.stderr)
            browser_engine = "chrome"
            # The if/elif/else chain entered this branch, so the elif/else below
            # will not execute. Handle Chrome / ready signalling explicitly here.
            if own_browser:
                async def _camoufox_fallback_chrome() -> None:
                    nonlocal chrome_proc
                    try:
                        chrome_proc = await _launch_chrome(port, user_data_dir, headless, proxy_url=proxy_url)
                        async def _drain():
                            assert chrome_proc.stderr
                            while True:
                                line = await chrome_proc.stderr.readline()
                                if not line:
                                    break
                        asyncio.create_task(_drain())
                        ready = await _wait_for_cdp(port, timeout_secs=90)
                        if ready:
                            print(f"Bridge: Chrome (fallback) ready at {cdp_url}", file=sys.stderr)
                    except Exception as exc:
                        print(f"Bridge: Chrome fallback launch error — {exc}", file=sys.stderr)
                    finally:
                        chrome_ready.set()
                asyncio.create_task(_camoufox_fallback_chrome())
                os.environ["BROWSER_CDP_URL"]     = cdp_url
                os.environ["MCP_BROWSER_CDP_URL"] = cdp_url
            else:
                chrome_ready.set()

    elif own_browser:
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
