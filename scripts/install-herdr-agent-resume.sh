#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=scripts/logging.sh
source "$SCRIPT_DIR/logging.sh"

if [[ "${SKIP_HERDR:-}" == "1" || "${SKIP_HERDR_AGENT_RESUME:-}" == "1" ]]; then
  log_step "Skipping Herdr agent resume (SKIP_HERDR or SKIP_HERDR_AGENT_RESUME=1)"
  exit 0
fi

if [[ ${EUID:-$(id -u)} -eq 0 ]]; then
  echo "Please run this script as your regular user (not root/sudo)." >&2
  exit 1
fi

case "${1:-}" in
  "") installer_args=(--update --auto --no-adopt) ;;
  --uninstall) installer_args=(--uninstall) ;;
  *) echo "Usage: $0 [--uninstall]" >&2; exit 1 ;;
esac
if (( $# > 1 )); then
  echo "Usage: $0 [--uninstall]" >&2
  exit 1
fi

# Deliberately pinned: review changes before moving this to a newer fork revision.
REPOSITORY="https://github.com/mortenvp/herdr-agent-resume.git"
REVISION="a62a3eeb9d2fc46f60490ecd44042b0a0b77cb28"
export PATH="$HOME/.local/bin:$PATH"
export HERDR_APP_HOME="${HERDR_APP_HOME:-${XDG_CONFIG_HOME:-$HOME/.config}/herdr-app}"

for tool in herdr-app hc; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "$tool is required; run scripts/install-herdr.sh first." >&2
    exit 1
  fi
done

missing_packages=()
for dependency in git:git python3:python; do
  if ! command -v "${dependency%%:*}" >/dev/null 2>&1; then
    missing_packages+=("${dependency#*:}")
  fi
done
if (( ${#missing_packages[@]} > 0 )); then
  log_step "Installing Herdr agent resume dependencies"
  sudo pacman -S --noconfirm --needed "${missing_packages[@]}"
fi

TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT
SOURCE_DIR="$TEMP_DIR/source"
log_step "Fetching Herdr agent resume from mortenvp/herdr-agent-resume ($REVISION)"
git -c core.hooksPath=/dev/null init --quiet "$SOURCE_DIR"
git -C "$SOURCE_DIR" remote add origin "$REPOSITORY"
git -C "$SOURCE_DIR" fetch --quiet --depth=1 origin "$REVISION"
git -C "$SOURCE_DIR" -c core.hooksPath=/dev/null checkout --quiet --detach FETCH_HEAD
if [[ "$(git -C "$SOURCE_DIR" rev-parse HEAD)" != "$REVISION" ]]; then
  echo "Unexpected Herdr agent resume revision; refusing to run the installer." >&2
  exit 1
fi

if [[ "${1:-}" != --uninstall ]]; then
  # Keep the pinned installer/backups, but fix Pi's eager session-path recording
  # and acknowledgement handling with our tested compatibility template.
  cp -- "$SCRIPT_DIR/herdr-pi-session-hook.js" "$SOURCE_DIR/scripts/pi_extension.js"
fi

# The upstream installer replaces file symlinks. Refuse those rather than breaking
# dotfile management. Also protect an unrelated same-named Pi extension.
python3 - "$HERDR_APP_HOME" <<'PY'
import os
from pathlib import Path
import sys

home = Path.home()
app = Path(sys.argv[1])
paths = [
    app / "keys.json",
    home / ".bashrc",
    Path(os.environ.get("ZDOTDIR") or home) / ".zshrc",
    home / ".config/fish/conf.d/agent-resume.fish",
    home / ".claude/settings.json",
    home / ".codex/hooks.json",
    home / ".grok/hooks/agent-resume.json",
    home / ".gemini/config/hooks.json",
    home / ".kiro/hooks/agent-resume.json",
]
extension = home / ".pi/agent/extensions/herdr-agent-resume.js"
for path in [*paths, extension, app / "mods/agent-resume"]:
    if path.is_symlink():
        raise SystemExit(f"Refusing to replace symlink: {path}")
if extension.exists() and "herdr-agent-resume pi session hook" not in extension.read_text():
    raise SystemExit(f"Refusing to overwrite an unrelated Pi extension: {extension}")
PY

if [[ "${1:-}" != --uninstall ]]; then
  # Fresh installs have not opened Herdr/Pi yet. Seed only absent files/directories;
  # the upstream installer requires keys.json and detects Pi/fish by their folders.
  mkdir -p "$HERDR_APP_HOME" "$HOME/.pi/agent"
  if [[ ! -e "$HERDR_APP_HOME/keys.json" ]]; then
    (set -o noclobber; printf '{}\n' > "$HERDR_APP_HOME/keys.json")
  fi
  if command -v fish >/dev/null 2>&1; then
    mkdir -p "$HOME/.config/fish/conf.d"
  fi
fi

log_step "Configuring Herdr agent resume (${installer_args[*]})"
python3 "$SOURCE_DIR/scripts/install.py" \
  --app-home "$HERDR_APP_HOME" --home "$HOME" "${installer_args[@]}"

if [[ "${1:-}" != --uninstall ]]; then
  log_step "Auto resume enabled. Pi sessions are recorded after the first saved message; existing Pi sessions need /reload. No core restart was performed."
fi
