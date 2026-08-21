#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=scripts/logging.sh
source "$SCRIPT_DIR/logging.sh"

log_step "Installing upstream tools"

if ! command -v curl >/dev/null 2>&1; then
  log_step "curl not found; installing curl"
  sudo pacman -S --noconfirm --needed curl
fi

"$SCRIPT_DIR/install-devbox.sh"
"$SCRIPT_DIR/install-uv.sh"
"$SCRIPT_DIR/install-tailscale.sh"
"$SCRIPT_DIR/install-pi-dev.sh"
"$SCRIPT_DIR/install-pi-agent-stuff.sh"
"$SCRIPT_DIR/install-playwright.sh"
