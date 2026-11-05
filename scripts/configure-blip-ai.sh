#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=scripts/logging.sh
source "$SCRIPT_DIR/logging.sh"

if [[ "${SKIP_BLIP_AI:-}" == "1" ]]; then
  log_step "Skipping Blip AI configuration (SKIP_BLIP_AI=1)"
  exit 0
fi

if [[ ${EUID:-$(id -u)} -eq 0 ]]; then
  echo "Please run this script as your regular user (not root/sudo)." >&2
  exit 1
fi

APPIMAGE="$HOME/.local/bin/BlipAI.AppImage"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"

if [[ ! -x "$APPIMAGE" ]]; then
  log_step "Blip AI AppImage is not installed; skipping launcher and autostart setup"
  exit 0
fi

TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

# Desktop Exec values have their own quoting rules (not shell quoting).
desktop_exec=${APPIMAGE//\\/\\\\}
desktop_exec=${desktop_exec//\"/\\\"}
desktop_exec=${desktop_exec//\`/\\\`}
desktop_exec=${desktop_exec//\$/\\\$}
desktop_exec=${desktop_exec//\\/\\\\}
desktop_exec=${desktop_exec//%/%%}
cat > "$TEMP_DIR/blip-ai.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Blip AI
Comment=AI voice dictation
Exec="$desktop_exec"
Icon=audio-input-microphone
Terminal=false
Categories=Utility;Accessibility;
EOF
install -Dm644 "$TEMP_DIR/blip-ai.desktop" "$DATA_HOME/applications/blip-ai.desktop"

cat >> "$TEMP_DIR/blip-ai.desktop" <<EOF
X-GNOME-Autostart-enabled=true
OnlyShowIn=GNOME;
EOF
install -Dm644 "$TEMP_DIR/blip-ai.desktop" "$CONFIG_HOME/autostart/blip-ai.desktop"

log_step "Configured Blip AI to start at the next GNOME login (including after a reboot)."
