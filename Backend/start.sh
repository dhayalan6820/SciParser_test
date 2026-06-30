#!/usr/bin/env bash
# Wrapper that exposes the Nix-store libraries Chromium (headless shell) needs
# before starting the Python backend.
#
# Chrome's unpatched binary requires these system libs — they live in the Nix
# store but aren't on LD_LIBRARY_PATH by default in Replit's sandbox.

set -e

# --------------------------------------------------------------------------
# Hardcoded Nix-store paths (stable-25_05, resolved 2026-06-30).
# Each entry below is: nix eval --raw nixpkgs#<pkg>
# If a path no longer exists (channel update), the script falls back to a
# dynamic nix-eval for that package automatically.
# --------------------------------------------------------------------------
declare -A PKG_PATHS=(
  ["nspr"]="/nix/store/gpb87pb8s826aggy1s3f352alp40dkj8-nspr-4.36"
  ["nss"]="/nix/store/2jsrwgic869zynqljiqa4g7dqzpwm2yd-nss-3.101.2"
  ["glib"]="/nix/store/y3nxdc2x8hwivppzgx5hkrhacsh87l21-glib-2.84.3"
  ["at-spi2-core"]="/nix/store/qrij2csr7p6jsfa40d7h4ckzqg4wd5w2-at-spi2-core-2.56.2"
  ["dbus.lib"]="/nix/store/231d6mmkylzr80pf30dbywa9x9aryjgy-dbus-1.14.10-lib"
  ["mesa-libgbm"]="/nix/store/24w3s75aa2lrvvxsybficn8y3zxd27kp-mesa-libgbm-25.1.0"
  ["xorg.libX11"]="/nix/store/1nsvsrqp5zm96r9p3rrq3yhlyw8jiy91-libX11-1.8.12"
  ["xorg.libXcomposite"]="/nix/store/4phl6z95v2i4525y0zpmi9v6ac0n4bx7-libXcomposite-0.4.6"
  ["xorg.libXdamage"]="/nix/store/h8143a07cf1vw41s49h0zahnq13zim94-libXdamage-1.1.6"
  ["xorg.libXext"]="/nix/store/0046rn5sgi6l38zl81bg2r02zlzxqqbc-libXext-1.3.6"
  ["xorg.libXfixes"]="/nix/store/94grp8dx897wmf0x3azpdbgzj3krz7v5-libXfixes-6.0.1"
  ["xorg.libXrandr"]="/nix/store/5fcbi2lycw2hz7rbn3nl5nrhhk2ki8dd-libXrandr-1.5.4"
  ["mesa"]="/nix/store/cpwib3zazj49fm0y04y53w4xkbqsgrgm-mesa-25.0.7"
  ["xorg.libxcb"]="/nix/store/2y2hhlki6macaj9j1409q1j6i33l6igf-libxcb-1.17.0"
  ["libxkbcommon"]="/nix/store/sisfq9wihyqqjzmrpik9b4xksifw97ha-libxkbcommon-1.8.1"
  ["alsa-lib"]="/nix/store/yw5xqn8lqinrifm9ij80nrmf0i6fdcbx-alsa-lib-1.2.13"
)

EXTRA_LD=""

for pkg in "${!PKG_PATHS[@]}"; do
  path="${PKG_PATHS[$pkg]}"

  # Fall back to dynamic resolution if the hardcoded path is stale
  if [ ! -d "$path" ]; then
    path=$(nix eval --raw "nixpkgs#$pkg" 2>/dev/null || true)
  fi

  if [ -d "$path/lib" ]; then
    EXTRA_LD="$EXTRA_LD:$path/lib"
  fi
done

# Prepend our Nix libs so they take priority over any (absent) system paths
export LD_LIBRARY_PATH="${EXTRA_LD#:}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

# Tell Playwright not to validate host requirements (we handle libs ourselves)
export PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=true

echo "[start.sh] LD_LIBRARY_PATH set (${#PKG_PATHS[@]} Nix lib paths injected)"

exec python3 run.py
