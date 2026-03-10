#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=./logging.sh
source "$SCRIPT_DIR/logging.sh"

KEYBINDINGS_PROFILE="${GNOME_KEYBINDINGS_PROFILE:-laptop}"
case "$KEYBINDINGS_PROFILE" in
  laptop)
    KEY_MODIFIER='<Control><Alt>'
    ;;
  desktop)
    KEY_MODIFIER='<Alt>'
    ;;
  *)
    printf "Error: Unsupported GNOME_KEYBINDINGS_PROFILE '%s'. Supported values: laptop, desktop.\n" "$KEYBINDINGS_PROFILE" >&2
    exit 1
    ;;
esac

if ! command -v gsettings >/dev/null 2>&1; then
  log_step "gsettings not available; skipping GNOME keybindings"
  exit 0
fi

log_step "Applying GNOME keybindings"
log_step "GNOME keybindings profile: $KEYBINDINGS_PROFILE (modifier: $KEY_MODIFIER)"

CUSTOM_TERMINAL_PATH='/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/'
CUSTOM_SCREENSHOT_PATH='/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom1/'

BIND_WWW_PRIMARY="${KEY_MODIFIER}w"
BIND_WWW_SECONDARY="${KEY_MODIFIER}m"
BIND_WORKSPACE_LEFT="${KEY_MODIFIER}Left"
BIND_WORKSPACE_RIGHT="${KEY_MODIFIER}Right"
BIND_TERMINAL="${KEY_MODIFIER}t"
BIND_SCREENSHOT="${KEY_MODIFIER}p"
BIND_CLOSE_WINDOW='<Alt>F4'

# Browser launcher shortcuts
gsettings set org.gnome.settings-daemon.plugins.media-keys www "['$BIND_WWW_PRIMARY', '$BIND_WWW_SECONDARY']"
gsettings set org.gnome.settings-daemon.plugins.media-keys email "[]"

# Workspace navigation
gsettings set org.gnome.desktop.wm.keybindings switch-to-workspace-left "['$BIND_WORKSPACE_LEFT']"
gsettings set org.gnome.desktop.wm.keybindings switch-to-workspace-right "['$BIND_WORKSPACE_RIGHT']"
gsettings set org.gnome.desktop.wm.keybindings close "['$BIND_CLOSE_WINDOW']"

# Terminal and screenshot launchers
gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings "['$CUSTOM_TERMINAL_PATH', '$CUSTOM_SCREENSHOT_PATH']"

gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:"$CUSTOM_TERMINAL_PATH" name 'Warp Terminal'
gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:"$CUSTOM_TERMINAL_PATH" command 'warp-terminal'
gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:"$CUSTOM_TERMINAL_PATH" binding "$BIND_TERMINAL"

gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:"$CUSTOM_SCREENSHOT_PATH" name 'Flameshot Capture'
gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:"$CUSTOM_SCREENSHOT_PATH" command 'xdotool exec flameshot gui'
gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:"$CUSTOM_SCREENSHOT_PATH" binding "$BIND_SCREENSHOT"
