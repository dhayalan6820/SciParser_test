---
name: Chrome LD_LIBRARY_PATH in Replit (Nix sandbox)
description: How to correctly set LD_LIBRARY_PATH for Playwright Chromium in the Replit Nix sandbox
---

## Rule
The Playwright Chromium binary at `.cache/ms-playwright/chromium-1228/chrome-linux64/chrome` requires 19 Nix store lib paths to start. Without them, Chrome exits with code 127 (`libnspr4.so`, `libcairo.so.2`, `libpango-1.0.so.0`, etc. not found).

**How to apply:** `Backend/start.sh` hardcodes all 19 paths, exports `LD_LIBRARY_PATH`, then `exec python3 run.py`. The FastAPI process and all its subprocesses (including the bridge subprocess and Chrome) inherit this env var automatically.

**Why:** The Replit Nix sandbox does not have these libs on the default LD_LIBRARY_PATH. Dynamic fallback via `nix eval` is included in start.sh if a hardcoded path becomes stale.

## Critical trap
Do NOT use `source start.sh` to capture LD_LIBRARY_PATH in a script — start.sh ends with `exec python3 run.py` which replaces the shell process, so any code after `source` never runs and the variable is captured as empty.

**Correct approach to get LD_LIBRARY_PATH outside of start.sh:** Build it manually from the hardcoded Nix paths in start.sh (see the declare -A PKG_PATHS block).

## Timing
Chrome takes ~2-4 seconds to show "DevTools listening on ws://..." even with correct libs. The bridge's `_wait_for_cdp` polls for up to 90 seconds (1-second intervals), which is sufficient. dbus errors in Chrome stderr are harmless — Chrome continues running.
