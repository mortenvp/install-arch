#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=scripts/logging.sh
source "$SCRIPT_DIR/logging.sh"

if [[ "${SKIP_GITHUB_TRAY:-}" == "1" ]]; then
  log_step "Skipping GitHub Tray configuration (SKIP_GITHUB_TRAY=1)"
  exit 0
fi

if [[ ${EUID:-$(id -u)} -eq 0 ]]; then
  echo "Please run this script as your regular user (not root/sudo)." >&2
  exit 1
fi

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
UUID="github-tray@debba.github.com"
if [[ ! -f "$DATA_HOME/gnome-shell/extensions/$UUID/metadata.json" ]] ||
    ! command -v gnome-extensions >/dev/null 2>&1; then
  log_step "GitHub Tray is not installed; skipping its settings launcher"
  exit 0
fi

TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT
cat > "$TEMP_DIR/github-tray-settings.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=GitHub Tray Settings
Comment=Configure GitHub Tray username, authentication, and preferences
Exec=gnome-extensions prefs github-tray@debba.github.com
TryExec=gnome-extensions
Icon=preferences-system
Terminal=false
Categories=GNOME;GTK;Settings;DesktopSettings;
OnlyShowIn=GNOME;
EOF
install -Dm644 "$TEMP_DIR/github-tray-settings.desktop" "$DATA_HOME/applications/github-tray-settings.desktop"

log_step "Added GitHub Tray Settings to the GNOME app launcher. Authentication is configured manually in that window."
