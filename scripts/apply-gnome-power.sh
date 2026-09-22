#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# Reuse hardware detection and logging without opening another profile prompt.
# shellcheck source=scripts/select-gnome-keybindings-profile.sh
source "$SCRIPT_DIR/select-gnome-keybindings-profile.sh"

POWER_PROFILE="${GNOME_KEYBINDINGS_PROFILE:-$(detect_gnome_keybindings_profile)}"
case "$POWER_PROFILE" in
  laptop)
    log_step "Laptop profile; leaving GNOME power settings unchanged"
    exit 0
    ;;
  desktop) ;;
  *)
    printf "Error: Unsupported GNOME_KEYBINDINGS_PROFILE '%s'. Supported values: laptop, desktop.\n" "$POWER_PROFILE" >&2
    exit 1
    ;;
esac

if ! command -v gsettings >/dev/null 2>&1; then
  log_step "gsettings not available; skipping GNOME power defaults"
  exit 0
fi

log_step "Disabling GNOME idle blanking, dimming, and automatic suspend for desktop"

gsettings set org.gnome.desktop.session idle-delay 0
gsettings set org.gnome.settings-daemon.plugins.power idle-dim false
# Cover both power sources (including desktops reporting a battery/UPS).
for power_source in ac battery; do
  gsettings set org.gnome.settings-daemon.plugins.power "sleep-inactive-${power_source}-type" 'nothing'
  gsettings set org.gnome.settings-daemon.plugins.power "sleep-inactive-${power_source}-timeout" 0
done
