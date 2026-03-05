#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=./logging.sh
source "$SCRIPT_DIR/logging.sh"

if ! command -v systemctl >/dev/null 2>&1; then
  log_step "systemctl not available; skipping bluetooth service enable"
  exit 0
fi

if [[ ! -d /run/systemd/system ]]; then
  log_step "systemd is not PID 1; skipping bluetooth service enable"
  exit 0
fi

log_step "Enabling bluetooth.service"
if [[ ! -e /usr/lib/systemd/system/bluetooth.service && ! -e /etc/systemd/system/bluetooth.service ]]; then
  log_step "bluetooth.service unit not found; skipping"
  exit 0
fi

sudo systemctl enable --now bluetooth.service
