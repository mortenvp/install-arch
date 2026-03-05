#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=./scripts/logging.sh
source "$ROOT_DIR/scripts/logging.sh"

log_step "Installing packages (pacman + AUR)"
"$ROOT_DIR/scripts/install-all.sh"

log_step "Applying config files"
"$ROOT_DIR/scripts/apply-config.sh"

if [[ "${SKIP_GNOME_KEYBINDINGS:-}" == "1" ]]; then
  log_step "Skipping GNOME keybindings (SKIP_GNOME_KEYBINDINGS=1)"
else
  "$ROOT_DIR/scripts/apply-gnome-keybindings.sh"
fi

if [[ "${SKIP_GNOME_WORKSPACES:-}" == "1" ]]; then
  log_step "Skipping GNOME workspace defaults (SKIP_GNOME_WORKSPACES=1)"
else
  "$ROOT_DIR/scripts/apply-gnome-workspaces.sh"
fi

if [[ "${SKIP_GNOME_THEME:-}" == "1" ]]; then
  log_step "Skipping GNOME theme defaults (SKIP_GNOME_THEME=1)"
else
  "$ROOT_DIR/scripts/apply-gnome-theme.sh"
fi

if command -v systemctl >/dev/null 2>&1; then
  log_step "Enabling Bluetooth service"
  "$ROOT_DIR/scripts/enable-bluetooth.sh"
else
  log_step "systemctl not available; skipping Bluetooth service enable"
fi

if [[ "${SKIP_SHELL:-}" == "1" ]]; then
  log_step "Skipping default shell change (SKIP_SHELL=1)"
else
  log_step "Setting default shell to fish"
  "$ROOT_DIR/scripts/set-default-shell.sh"
fi

if [[ "${SKIP_GNOME_EXTENSIONS:-}" == "1" ]]; then
  log_step "Skipping GNOME extension enable (SKIP_GNOME_EXTENSIONS=1)"
else
  if command -v gnome-extensions >/dev/null 2>&1; then
    log_step "Enabling GNOME extensions"
    "$ROOT_DIR/scripts/enable-gnome-extensions.sh"
  else
    log_step "gnome-extensions not available; skipping"
  fi
fi
