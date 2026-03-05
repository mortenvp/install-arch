#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=./logging.sh
source "$SCRIPT_DIR/logging.sh"

if ! command -v gsettings >/dev/null 2>&1; then
  log_step "gsettings not available; skipping GNOME workspace defaults"
  exit 0
fi

log_step "Applying GNOME workspace defaults"

gsettings set org.gnome.mutter dynamic-workspaces false
gsettings set org.gnome.desktop.wm.preferences num-workspaces 8
