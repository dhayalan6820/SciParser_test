# Anti-Bot Stealth: All Options (No Proxy)

## What & Why
Frontier.com (and similar sites with DataDome/Akamai) detect the browser as automated. Without a residential proxy, we fix every other detectable signal: browser fingerprint leaks, CDP artifacts, headless rendering tells, missing browser features, and fresh-profile suspicion. This implements Options B, C, D, and E.

## Done looks like
- The browser injects stealth JS on every new page before any content loads (hides `navigator.webdriver`, CDP runtime artifacts, canvas fingerprint, WebGL, plugins, permissions API, chrome runtime)
- The user-profile directory is persistent across runs (fixed path, not a temp dir) so cookies and history accumulate naturally
- Camoufox is installed and selectable as the browser engine via an env var `BROWSER_ENGINE=camoufox`, falling back to Chrome when not set
- Additional Chrome flags are added to reduce headless-specific rendering artifacts
- The ATAG prompt instructs the agent to move the mouse naturally before clicking, scroll before interacting, and add random delays

## Out of scope
- Residential or datacenter proxies
- Solving CAPTCHAs (handled by the separate memory/CAPTCHA system)
- Changing the LLM or agent pipeline

## Steps

1. **Persistent user-data-dir** — Change `BROWSER_USER_DATA_DIR` default from `tempfile.mkdtemp(...)` to a fixed path (`~/.config/browser-use/profile`) so cookies, localStorage, and history survive between runs. Create the directory if it doesn't exist.

2. **JS stealth injection patch** — After `BrowserSession.start()` succeeds, monkey-patch the Playwright page creation so that every new page runs a stealth init script before navigation. The script must:
   - Delete `navigator.webdriver` / make it return `undefined`
   - Remove CDP runtime artifacts: `window.__playwright`, `window.__pwInitScripts`, `window.__PWDEBUGGER__`, `cdc_*` globals
   - Spoof `navigator.plugins` with realistic PDF/Chrome PDF/Native Client entries
   - Spoof `navigator.languages` as `["en-US", "en"]`
   - Override `HTMLCanvasElement.prototype.toDataURL` and `getContext("2d").getImageData` with slight random noise per session
   - Override WebGL `RENDERER` and `VENDOR` strings to a realistic GPU (e.g., "ANGLE (NVIDIA, NVIDIA GeForce GTX 1650...)")
   - Spoof `window.chrome.runtime` to exist (non-headless Chrome has it; headless does not)
   - Override `Notification.permission` to `"default"` instead of `"denied"`
   - Set `screen.width/height` and `window.outerWidth/outerHeight` to the window size

3. **Additional Chrome launch flags** — Add flags to reduce headless-specific rendering differences:
   - `--window-size=1920,1080` (upgrade from 1280×800 to a more common resolution)
   - `--start-maximized`
   - `--force-color-profile=srgb`
   - `--disable-features=IsolateOrigins,site-per-process`
   - Remove `--disable-gpu` when not in headless mode (GPU helps WebGL look real)
   - Add `--password-store=basic` to suppress keyring prompts

4. **Camoufox integration (Option C)** — Add a `BROWSER_ENGINE=camoufox` path in the bridge:
   - Install `camoufox` Python package and fetch the browser binary (`python -m camoufox fetch`)
   - When `BROWSER_ENGINE=camoufox`, launch via `camoufox.AsyncNewBrowser(headless=headless)` context manager instead of the Chrome subprocess
   - Camoufox returns a Playwright `Browser` object — extract its WebSocket endpoint and pass it as `cdp_url` to `BrowserSession`, or connect via `playwright.firefox.connect(ws_endpoint)`
   - Chrome-specific flags and user-agent spoofing are skipped when Camoufox is active (it handles fingerprinting internally)
   - Keep the existing Chrome path as the default so nothing breaks without the env var

5. **ATAG prompt update** — Add a stealth behavior section to the ATAG system prompt instructing the agent to: scroll the page before clicking, move the mouse to the element first (use `browser_hover`), add a `browser_wait` of 200–600 ms between actions, and avoid clicking immediately after page load

## Relevant files
- `Backend/src/agents/browser_use_bridge.py`
- `Backend/src/services/ATAG.py`
- `Backend/requirements.txt`
- `Backend/pyproject.toml`
