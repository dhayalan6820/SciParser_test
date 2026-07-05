#!/usr/bin/env bash
# Local-desktop equivalent of start.sh, minus the Replit-sandbox-specific
# Nix library path wiring (start.sh's LD_LIBRARY_PATH block only applies to
# Replit's Nix-based filesystem — on a normal desktop OS, Chrome/Camoufox
# find their system libraries the regular way via your OS package manager,
# so none of that is needed here).
#
# Use this instead of start.sh when running the backend on your own machine:
#   bash start.local.sh

set -e

# Tell Playwright not to run its own host-requirements validation.
export PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=true

# Disable CrewAI's telemetry/trace-viewer prompt — it can block on stdin in
# non-interactive terminals (it asks "view traces? y/N" with no way to answer).
export CREWAI_DISABLE_TELEMETRY=true
export OTEL_SDK_DISABLED=true

# ---------------------------------------------------------------------------
# Camoufox browser binary bootstrap
# Only runs when BROWSER_ENGINE=camoufox (the default). Safe to re-run — it
# no-ops if the binary is already downloaded. If you're using
# BROWSER_ENGINE=browser-use instead, make sure you've run
# `playwright install chromium` once yourself.
# ---------------------------------------------------------------------------
if [ "${BROWSER_ENGINE:-camoufox}" = "camoufox" ]; then
    echo "[start.local.sh] BROWSER_ENGINE=camoufox — fetching camoufox browser binary (no-op if already installed)..."
    python3 -m camoufox fetch || echo "[start.local.sh] WARNING: camoufox fetch failed — camoufox mode may not work"
fi

echo "[start.local.sh] Starting backend..."
exec python3 run.py
