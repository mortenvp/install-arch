#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=./logging.sh
source "$SCRIPT_DIR/logging.sh"

if ! command -v gsettings >/dev/null 2>&1; then
  log_step "gsettings not available; skipping Arch Update Indicator defaults"
  exit 0
fi

if ! gsettings list-schemas | grep -qx 'org.gnome.shell.extensions.arch-update'; then
  log_step "Arch Update Indicator schema not found; skipping defaults"
  exit 0
fi

check_cmd="/bin/sh -c \"(/usr/bin/checkupdates; /usr/bin/yay -Qu --color never | sed 's/Get .*//') | sort -u -t' ' -k1,1\""

if command -v kgx >/dev/null 2>&1; then
  update_cmd="kgx -e '/bin/sh -c \"yay ; echo Done - Press enter to exit; read _\"'"
elif command -v gnome-terminal >/dev/null 2>&1; then
  update_cmd="gnome-terminal -- /bin/sh -c \"yay ; echo Done - Press enter to exit; read _\""
else
  update_cmd="yay"
fi

log_step "Configuring Arch Update Indicator defaults for yay"
gsettings set org.gnome.shell.extensions.arch-update check-cmd "$check_cmd"
gsettings set org.gnome.shell.extensions.arch-update update-cmd "$update_cmd"
