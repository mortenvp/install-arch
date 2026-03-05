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

mapfile -t installed_extensions < <(gnome-extensions list)

enabled_any=0

if printf '%s\n' "${installed_extensions[@]}" | grep -q "^${POP_SHELL_UUID}$"; then
  log_step "Enabling Pop Shell (${POP_SHELL_UUID})"
  gnome-extensions enable "$POP_SHELL_UUID"
  enabled_any=1
else
  log_step "Pop Shell extension not found; skipping"
fi

appindicator_uuid="$(printf '%s\n' "${installed_extensions[@]}" | grep '^appindicatorsupport@' | head -n 1 || true)"
if [[ -n "$appindicator_uuid" ]]; then
  log_step "Enabling AppIndicator (${appindicator_uuid})"
  gnome-extensions enable "$appindicator_uuid"
  enabled_any=1
else
  if [[ -d /usr/share/gnome-shell/extensions/appindicatorsupport@rgcjonas.gmail.com ]]; then
    log_step "AppIndicator is installed but not visible to the current GNOME Shell session; log out/in and run this script again"
  else
    log_step "AppIndicator extension not found; skipping"
  fi
fi

if [[ "$enabled_any" -eq 0 ]]; then
  log_step "No target GNOME extensions found to enable"
fi
