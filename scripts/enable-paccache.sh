#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=scripts/logging.sh
source "$SCRIPT_DIR/logging.sh"

if ! command -v systemctl >/dev/null 2>&1; then
  log_step "systemctl not available; skipping paccache timer enable"
  exit 0
fi

if [[ ! -d /run/systemd/system ]]; then
  log_step "systemd is not PID 1; skipping paccache timer enable"
  exit 0
fi

log_step "Enabling paccache.timer"
if [[ ! -e /usr/lib/systemd/system/paccache.timer && ! -e /etc/systemd/system/paccache.timer ]]; then
  log_step "paccache.timer unit not found; skipping"
  exit 0
fi

is_enabled="$(systemctl is-enabled paccache.timer 2>/dev/null || true)"
is_active="$(systemctl is-active paccache.timer 2>/dev/null || true)"
if [[ "$is_enabled" == "enabled" && "$is_active" == "active" ]]; then
  log_step "paccache.timer already enabled and active; skipping"
  exit 0
fi

sudo systemctl enable --now paccache.timer
