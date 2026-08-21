#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=scripts/logging.sh
source "$SCRIPT_DIR/logging.sh"

if ! command -v gsettings >/dev/null 2>&1; then
  log_step "gsettings not available; skipping Arch Update Indicator defaults"
  exit 0
fi

if ! gsettings list-schemas | grep -qx 'org.gnome.shell.extensions.arch-update'; then
  log_step "Arch Update Indicator schema not found; skipping defaults"
  exit 0
fi

npm_prefix="\$HOME/.local"
npm_env="NPM_CONFIG_PREFIX=$npm_prefix PATH=$npm_prefix/bin:\$PATH"
cleanup_script="$SCRIPT_DIR/cleanup-npm-global-conflicts.sh"
pi_agent_stuff_script="$SCRIPT_DIR/install-pi-agent-stuff.sh"
pi_agent_stuff_check_script="$SCRIPT_DIR/check-pi-agent-stuff-update.sh"

check_cmd="/bin/sh -c \"(/usr/bin/checkupdates; /usr/bin/yay -Qu --color never | sed 's/Get .*//'; if command -v npm >/dev/null 2>&1; then $npm_env npm outdated -g --depth=0 --json 2>/dev/null | node -e 'let data=\\\"\\\"; process.stdin.on(\\\"data\\\", c => data += c).on(\\\"end\\\", () => { if (!data.trim()) return; const updates = JSON.parse(data); for (const [name, meta] of Object.entries(updates)) { console.log(\\\"npm-\\\" + name + \\\" \\\" + meta.current + \\\" -> \\\" + meta.latest); } });' 2>/dev/null || true; fi; $pi_agent_stuff_check_script) | sort -u -t' ' -k1,1\""

update_body="$cleanup_script && yay && if command -v npm >/dev/null 2>&1; then mkdir -p $npm_prefix; $npm_env npm update -g; fi && if ! $pi_agent_stuff_script; then echo Failed to refresh personal Pi package. >&2; fi"

if command -v gnome-terminal >/dev/null 2>&1; then
  # Keep an interactive shell open after updates so the terminal never lands in
  # a read-only "Command exited" view because of profile/terminal behavior.
  update_cmd="gnome-terminal -- /bin/bash -lc \"$update_body; exec /bin/bash -i\""
elif command -v kgx >/dev/null 2>&1; then
  # kgx command mode can land in a read-only "Command exited" state. Keeping an
  # interactive shell open after yay avoids that state.
  update_cmd="kgx -e '/bin/bash -lc \"$update_body; exec /bin/bash -i\"'"
else
  update_cmd="/bin/bash -lc \"$update_body\""
fi

log_step "Configuring Arch Update Indicator defaults for yay + user-local npm"
gsettings set org.gnome.shell.extensions.arch-update check-cmd "$check_cmd"
gsettings set org.gnome.shell.extensions.arch-update update-cmd "$update_cmd"
