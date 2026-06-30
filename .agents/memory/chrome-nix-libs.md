---
name: Chrome Nix libs for Playwright
description: How to make pip-installed Playwright's chrome-headless-shell find its system libs in the Replit Nix sandbox (stable-25_05).
---

The chrome-headless-shell binary downloaded by `pip install playwright` + `playwright install chromium` is an unpatched Linux binary that requires 16 system `.so` files not on `LD_LIBRARY_PATH` by default in the Nix sandbox. `Backend/start.sh` sets all of them before exec-ing `python3 run.py`.

**Why:** Nix installs libs at content-addressed store paths, not `/lib` or `/usr/lib`. The binary's dynamic linker can't find them unless LD_LIBRARY_PATH points into those store dirs.

**How to apply:** Any time the backend is restarted, it must go through `start.sh` (workflow command: `cd Backend && bash start.sh`). Direct `python3 run.py` will not work for browser-use features.

**Key gotchas discovered:**
1. `dbus` → wrong output; must use `dbus.lib` = `/nix/store/231d6mmkylzr80pf30dbywa9x9aryjgy-dbus-1.14.10-lib`
2. `libgbm.so.1` is NOT in `mesa` or `mesa.drivers`; it lives in the separate `mesa-libgbm` package = `/nix/store/24w3s75aa2lrvvxsybficn8y3zxd27kp-mesa-libgbm-25.1.0`
3. After `ldd chrome-headless-shell | grep "not found"` returns nothing, Chrome launches fine.
4. The `playwright install` command returns exit 0 silently if browsers are already installed, so check `~/.cache/ms-playwright/` to confirm.

**Verification command:**
```bash
env LD_LIBRARY_PATH="<paths>" ldd ~/.cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell 2>&1 | grep "not found"
# should produce no output (grep exits 1 = all resolved)
```

**Remaining separate issue:** browser-use's `BrowserStateRequestEvent` watchdog raises "Expected at least one handler to return a non-None result" — this is an internal browser-use bug, NOT a Chrome launch failure. The agent falls back to search tools and still returns responses.
