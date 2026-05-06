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

check_cmd="/bin/sh -c \"(/usr/bin/checkupdates; /usr/bin/yay -Qu --color never | sed 's/Get .*//'; if command -v npm >/dev/null 2>&1; then npm outdated -g --depth=0 --json 2>/dev/null | node -e 'let data=\\\"\\\"; process.stdin.on(\\\"data\\\", c => data += c).on(\\\"end\\\", () => { if (!data.trim()) return; const updates = JSON.parse(data); for (const [name, meta] of Object.entries(updates)) { console.log(\\\"npm-\\\" + name + \\\" \\\" + meta.current + \\\" -> \\\" + meta.latest); } });' 2>/dev/null || true; fi) | sort -u -t' ' -k1,1\""

if command -v gnome-terminal >/dev/null 2>&1; then
  # Keep an interactive shell open after updates so the terminal never lands in
  # a read-only "Command exited" view because of profile/terminal behavior.
  update_cmd="gnome-terminal -- /bin/bash -lc \"yay; if command -v npm >/dev/null 2>&1; then sudo npm update -g; fi; exec /bin/bash -i\""
elif command -v kgx >/dev/null 2>&1; then
  # kgx command mode can land in a read-only "Command exited" state. Keeping an
  # interactive shell open after yay avoids that state.
  update_cmd="kgx -e '/bin/bash -lc \"yay; if command -v npm >/dev/null 2>&1; then sudo npm update -g; fi; exec /bin/bash -i\"'"
else
  update_cmd="/bin/bash -lc \"yay; if command -v npm >/dev/null 2>&1; then sudo npm update -g; fi\""
fi

log_step "Configuring Arch Update Indicator defaults for yay + npm"
gsettings set org.gnome.shell.extensions.arch-update check-cmd "$check_cmd"
gsettings set org.gnome.shell.extensions.arch-update update-cmd "$update_cmd"
