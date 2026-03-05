#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=./logging.sh
source "$SCRIPT_DIR/logging.sh"

if ! command -v gsettings >/dev/null 2>&1; then
  log_step "gsettings not available; skipping GNOME keybindings"
  exit 0
fi

log_step "Applying GNOME keybindings"

CUSTOM_TERMINAL_PATH='/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/'
CUSTOM_SCREENSHOT_PATH='/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom1/'

# Browser launcher shortcuts
gsettings set org.gnome.settings-daemon.plugins.media-keys www "['<Control><Alt>w', '<Control><Alt>m']"
gsettings set org.gnome.settings-daemon.plugins.media-keys email "[]"

# Workspace navigation
gsettings set org.gnome.desktop.wm.keybindings switch-to-workspace-left "['<Control><Alt>Left']"
gsettings set org.gnome.desktop.wm.keybindings switch-to-workspace-right "['<Control><Alt>Right']"

# Terminal and screenshot launchers
gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings "['$CUSTOM_TERMINAL_PATH', '$CUSTOM_SCREENSHOT_PATH']"

gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:"$CUSTOM_TERMINAL_PATH" name 'Warp Terminal'
gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:"$CUSTOM_TERMINAL_PATH" command 'warp-terminal'
gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:"$CUSTOM_TERMINAL_PATH" binding '<Control><Alt>t'

gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:"$CUSTOM_SCREENSHOT_PATH" name 'Flameshot Capture'
gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:"$CUSTOM_SCREENSHOT_PATH" command 'xdotool exec flameshot gui'
gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:"$CUSTOM_SCREENSHOT_PATH" binding '<Control><Alt>p'
