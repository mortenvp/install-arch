#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=scripts/logging.sh
source "$SCRIPT_DIR/logging.sh"

if ! command -v gsettings >/dev/null 2>&1; then
  log_step "gsettings not available; skipping GNOME keybindings"
  exit 0
fi

KEYBINDINGS_PROFILE=$("$SCRIPT_DIR/select-gnome-keybindings-profile.sh")
case "$KEYBINDINGS_PROFILE" in
  laptop)
    KEY_MODIFIER='<Control><Alt>'
    OVERLAY_KEY='Super'
    ;;
  desktop)
    KEY_MODIFIER='<Alt>'
    OVERLAY_KEY='Super_L'
    ;;
  *)
    printf "Error: Unsupported GNOME_KEYBINDINGS_PROFILE '%s'. Supported values: laptop, desktop.\n" "$KEYBINDINGS_PROFILE" >&2
    exit 1
    ;;
esac

log_step "Applying GNOME keybindings"
log_step "GNOME keybindings profile: $KEYBINDINGS_PROFILE (modifier: $KEY_MODIFIER, overlay: $OVERLAY_KEY)"

CUSTOM_TERMINAL_PATH='/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/'
CUSTOM_SCREENSHOT_PATH='/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom1/'
CUSTOM_FILES_PATH='/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom2/'

BIND_WWW_PRIMARY="${KEY_MODIFIER}w"
BIND_WWW_SECONDARY="${KEY_MODIFIER}m"
BIND_HOME="${KEY_MODIFIER}f"
BIND_WORKSPACE_LEFT="${KEY_MODIFIER}Left"
BIND_WORKSPACE_RIGHT="${KEY_MODIFIER}Right"
BIND_TERMINAL="${KEY_MODIFIER}t"
BIND_SCREENSHOT="${KEY_MODIFIER}p"
BIND_CLOSE_WINDOW='<Alt>F4'

# Browser launcher shortcuts
gsettings set org.gnome.settings-daemon.plugins.media-keys www "['$BIND_WWW_PRIMARY', '$BIND_WWW_SECONDARY']"
gsettings set org.gnome.settings-daemon.plugins.media-keys email "[]"
# Use a custom Files launcher below to force a new window instead of a tab.
gsettings set org.gnome.settings-daemon.plugins.media-keys home "[]"

# Workspace navigation
gsettings set org.gnome.desktop.wm.keybindings switch-to-workspace-left "['$BIND_WORKSPACE_LEFT']"
gsettings set org.gnome.desktop.wm.keybindings switch-to-workspace-right "['$BIND_WORKSPACE_RIGHT']"
gsettings set org.gnome.desktop.wm.keybindings close "['$BIND_CLOSE_WINDOW']"

# Overview overlay key
gsettings set org.gnome.mutter overlay-key "$OVERLAY_KEY"

# Terminal, screenshot, and Files launchers
gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings "['$CUSTOM_TERMINAL_PATH', '$CUSTOM_SCREENSHOT_PATH', '$CUSTOM_FILES_PATH']"

gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:"$CUSTOM_TERMINAL_PATH" name 'Warp Terminal'
gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:"$CUSTOM_TERMINAL_PATH" command 'warp-terminal'
gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:"$CUSTOM_TERMINAL_PATH" binding "$BIND_TERMINAL"

gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:"$CUSTOM_SCREENSHOT_PATH" name 'Flameshot Capture'
gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:"$CUSTOM_SCREENSHOT_PATH" command 'xdotool exec flameshot gui'
gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:"$CUSTOM_SCREENSHOT_PATH" binding "$BIND_SCREENSHOT"

gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:"$CUSTOM_FILES_PATH" name 'Files (New Window)'
gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:"$CUSTOM_FILES_PATH" command 'nautilus --new-window'
gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:"$CUSTOM_FILES_PATH" binding "$BIND_HOME"
