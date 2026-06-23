#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=scripts/logging.sh
source "$SCRIPT_DIR/logging.sh"

if ! command -v wpctl >/dev/null 2>&1; then
  log_step "wpctl not available; skipping audio defaults"
  exit 0
fi

if ! wpctl settings >/dev/null 2>&1; then
  log_step "No active PipeWire/WirePlumber user session; skipping audio defaults"
  exit 0
fi

log_step "Disabling Bluetooth auto-switch to headset profile"
wpctl settings --save bluetooth.autoswitch-to-headset-profile false
