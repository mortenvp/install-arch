#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=./logging.sh
source "$SCRIPT_DIR/logging.sh"

if ! command -v systemctl >/dev/null 2>&1; then
  log_step "systemctl not available; skipping sshd service enable"
  exit 0
fi

if [[ ! -d /run/systemd/system ]]; then
  log_step "systemd is not PID 1; skipping sshd service enable"
  exit 0
fi

log_step "Enabling sshd.service"
if [[ ! -e /usr/lib/systemd/system/sshd.service && ! -e /etc/systemd/system/sshd.service ]]; then
  log_step "sshd.service unit not found; skipping"
  exit 0
fi

is_enabled="$(systemctl is-enabled sshd.service 2>/dev/null || true)"
is_active="$(systemctl is-active sshd.service 2>/dev/null || true)"
if [[ "$is_enabled" == "enabled" && "$is_active" == "active" ]]; then
  log_step "sshd.service already enabled and active; skipping"
  exit 0
fi

sudo systemctl enable --now sshd.service
