#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=./logging.sh
source "$SCRIPT_DIR/logging.sh"

if ! command -v systemctl >/dev/null 2>&1; then
  log_step "systemctl not available; skipping GDM monitor sync setup"
  exit 0
fi

if [[ ! -d /run/systemd/system ]]; then
  log_step "systemd is not PID 1; skipping GDM monitor sync setup"
  exit 0
fi

if [[ ! -e /usr/lib/systemd/system/gdm.service && ! -e /etc/systemd/system/gdm.service ]]; then
  log_step "gdm.service unit not found; skipping GDM monitor sync setup"
  exit 0
fi

SOURCE_MONITORS_XML="$HOME/.config/monitors.xml"
DROP_IN_DIR="/etc/systemd/system/gdm.service.d"
DROP_IN_FILE="$DROP_IN_DIR/override.conf"

log_step "Installing GDM monitor sync drop-in"
sudo install -d -m 755 "$DROP_IN_DIR"
sudo tee "$DROP_IN_FILE" >/dev/null <<EOF
[Service]
ExecStartPre=/bin/sh -c 'if [ -r "$SOURCE_MONITORS_XML" ]; then /bin/install -d -m 755 /etc/xdg && /bin/install -m 644 "$SOURCE_MONITORS_XML" /etc/xdg/monitors.xml; fi'
EOF

sudo systemctl daemon-reload
log_step "Installed $DROP_IN_FILE"

if [[ -f "$SOURCE_MONITORS_XML" ]]; then
  bash "$SCRIPT_DIR/sync-gdm-monitors.sh" "$SOURCE_MONITORS_XML"
fi
