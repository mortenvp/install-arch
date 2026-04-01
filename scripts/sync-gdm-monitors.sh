#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=./logging.sh
source "$SCRIPT_DIR/logging.sh"

SOURCE_MONITORS_XML=${1:-"$HOME/.config/monitors.xml"}
TARGET_MONITORS_XML="/etc/xdg/monitors.xml"

if [[ ! -f "$SOURCE_MONITORS_XML" ]]; then
  log_step "No monitors.xml at $SOURCE_MONITORS_XML; skipping GDM monitor sync"
  exit 0
fi

log_step "Syncing monitor layout to $TARGET_MONITORS_XML"
sudo install -d -m 755 /etc/xdg
sudo install -m 644 "$SOURCE_MONITORS_XML" "$TARGET_MONITORS_XML"
