---
name: browser-stealth
description: >
  Browser fingerprint spoofing and anti-detection system — stealth JavaScript
  injection, Playwright marker removal, and real Chrome CDP connection strategy
  to avoid bot detection by DataDome, Cloudflare, Akamai, and PerimeterX.
---

## What It Does

Every browser session needs to avoid detection by anti-bot systems. This skill covers:
1. **Stealth JS injection**: Patches browser APIs to hide automation markers
2. **Real Chrome connection**: Using the user's actual Chrome browser via CDP instead
   of Playwright's bundled Chromium (eliminates fingerprinting entirely)
3. **Human-like behavior**: Timing delays between actions (specified in agent specs)

## Runtime Files

- **Stealth JS**: [browser_use_bridge.py](file:///d:/Project/SciParser/Backend/src/agents/browser_use_bridge.py#L42-L57)
  — `STEALTH_JS` constant injected via `page.add_init_script()`.
- **Browser Launch**: [browser_use_bridge.py](file:///d:/Project/SciParser/Backend/src/agents/browser_use_bridge.py#L179-L250)
  — `run_bridge()` function: reads config, launches BrowserSession, injects stealth JS.
- **Config**: [config.py](file:///d:/Project/SciParser/Backend/src/config.py#L179-L222)
  — `BROWSER_ENGINE`, `BROWSER_EXECUTABLE_PATH` (from `.env`), `BROWSER_USER_DATA_DIR`,
  `browser_use_own_browser()`, CDP port/URL overrides.
- **Environment**: [.env](file:///d:/Project/SciParser/Backend/.env)
  — `BROWSER_EXECUTABLE_PATH`, `BROWSER_USER_DATA_DIR`, `BROWSER_PROFILE_DIRECTORY`,
  `BROWSER_USE_HEADLESS`, `BROWSER_ENGINE`.
- **Stealth Rules in Specs**: [browser.agent.md](file:///d:/Project/SciParser/Backend/src/agents/specs/browser.agent.md)
  — "Stealth Behavior" section (hover before click, 200-600ms delays, etc.).

## Current Stealth JS Coverage

The existing `STEALTH_JS` patches only 4 signals:
1. `navigator.webdriver` → undefined
2. Deletes `__playwright`, `__pwInitScripts`, `__PWDEBUGGER__`
3. Deletes `cdc_` prefixed properties
4. Sets `navigator.languages` → `['en-US', 'en']`

## What Modern Anti-Bot Systems Also Check

- `navigator.plugins` (empty in headless/Playwright)
- `navigator.permissions` API behavior
- WebGL vendor/renderer strings
- `window.chrome` runtime object
- `Notification.permission` behavior
- Canvas fingerprint consistency
- CDP protocol detection via `Runtime.evaluate`
- User-Agent consistency with actual browser version
- `window.outerHeight/outerWidth` (0 in headless)
- `navigator.connection` (missing in automation)

## Best Anti-Detection Strategy

**Use the user's real Chrome browser via CDP** — configured in `.env`:
```
BROWSER_EXECUTABLE_PATH=C:/Program Files/Google/Chrome/Application/chrome.exe
BROWSER_USER_DATA_DIR=C:/Users/.../AppData/Local/Google/Chrome/User Data
BROWSER_PROFILE_DIRECTORY=Default
```

When real Chrome is used, the fingerprint is 100% genuine — no stealth JS needed.
Stealth JS is the fallback for environments without a real Chrome installation.

## Common Issues

- **Playwright detection**: Sites like DataDome detect Playwright's Chromium binary even
  with stealth JS — the binary itself has different characteristics.
- **Profile locking**: Using the user's Chrome profile while Chrome is already running
  causes "profile locked" errors. Each session needs its own `--user-data-dir`.
- **Camoufox fallback**: The bridge tries Camoufox (Firefox-based) but falls back to
  Chrome because Firefox doesn't support the `/json/version` CDP endpoint that browser-use needs.
