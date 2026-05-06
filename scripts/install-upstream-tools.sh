#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=./logging.sh
source "$SCRIPT_DIR/logging.sh"

log_step "Installing upstream tools"

if ! command -v curl >/dev/null 2>&1; then
  log_step "curl not found; installing curl"
  sudo pacman -S --noconfirm --needed curl
fi

"$SCRIPT_DIR/install-lix.sh"
"$SCRIPT_DIR/install-devbox.sh"
"$SCRIPT_DIR/install-uv.sh"
"$SCRIPT_DIR/install-tailscale.sh"
"$SCRIPT_DIR/install-pi-dev.sh"
