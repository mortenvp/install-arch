#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=./logging.sh
source "$SCRIPT_DIR/logging.sh"

if ! command -v gnome-extensions >/dev/null 2>&1; then
  echo "gnome-extensions not found. Install GNOME and gnome-shell extensions tooling." >&2
  exit 1
fi

POP_SHELL_UUID="pop-shell@system76.com"

if gnome-extensions list | grep -q "^${POP_SHELL_UUID}$"; then
  log_step "Enabling Pop Shell (${POP_SHELL_UUID})"
  gnome-extensions enable "$POP_SHELL_UUID"
else
  echo "Pop Shell extension not found: ${POP_SHELL_UUID}" >&2
  echo "Make sure gnome-shell-extension-pop-shell-git is installed." >&2
  exit 1
fi
