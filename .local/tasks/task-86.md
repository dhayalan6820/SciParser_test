---
title: Switch default browser to Camoufox to beat bot detection
---
# Switch Default Browser to Camoufox

## What & Why
Headless Chrome is the primary reason automation gets bot-detected. Sites fingerprint the headless flag, missing GPU, and other headless-only signals. Camoufox is a Firefox-based browser purpose-built to defeat these fingerprints — it patches over 10 known detection vectors internally. It's already supported in the codebase but Chrome headless is still the default. This task makes Camoufox the default and adds a UI control so users can switch engines if needed.

## Done looks like
- The browser launched by default is Camoufox (Firefox-based, stealth mode)
- If Camoufox fails to start, it automatically falls back to Chrome (already implemented)
- The settings panel shows a "Browser Engine" option letting users choose between Camoufox (recommended) and Chrome
- The active engine is visible somewhere in the UI (e.g. a small label or indicator during a session)
- Existing `BROWSER_ENGINE` env var still works as an override for self-hosted users

## Out of scope
- Changing how the local browser CDP connection works
- Proxy settings
- Non-headless Chrome (requires a display server not available in the Replit environment)

## Steps
1. **Change the default engine** — Flip the `BROWSER_ENGINE` default from `chrome` to `camoufox` in `run_bridge()`. No other logic changes needed since the fallback chain is already in place.
2. **Add a browser engine setting to the UI** — Add a "Browser Engine" selector to the settings/configuration panel with two options: "Camoufox – stealth Firefox (recommended)" and "Chrome – headless Chromium". Persist the choice and pass it as `BROWSER_ENGINE` when spawning the bridge.
3. **Show the active engine in the session UI** — Display which engine is running (e.g. a small badge or footer label like "Firefox · Camoufox" or "Chrome · headless") so users can confirm what's active.

## Relevant files
- `Backend/src/agents/browser_use_bridge.py:1288-1451`