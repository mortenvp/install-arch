#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=./scripts/logging.sh
source "$ROOT_DIR/scripts/logging.sh"

if [[ ${EUID:-$(id -u)} -eq 0 ]]; then
  echo "Please run install.sh as your regular user (not root/sudo)." >&2
  echo "Running as root will copy user config files (including fish) into /root." >&2
  exit 1
fi

log_step "Installing packages (pacman + AUR)"
"$ROOT_DIR/scripts/install-all.sh"

if [[ "${SKIP_HW_CODECS:-}" == "1" ]]; then
  log_step "Skipping hardware codec setup (SKIP_HW_CODECS=1)"
else
  log_step "Installing hardware codec support"
  "$ROOT_DIR/scripts/install-hw-codecs.sh"
fi

log_step "Applying config files"
"$ROOT_DIR/scripts/apply-config.sh"

if [[ "${SKIP_VSCODE_EXTENSIONS:-}" == "1" ]]; then
  log_step "Skipping VS Code extension setup (SKIP_VSCODE_EXTENSIONS=1)"
else
  log_step "Installing VS Code extensions"
  "$ROOT_DIR/scripts/install-vscode-extensions.sh"

  log_step "Configuring VS Code keybindings"
  "$ROOT_DIR/scripts/configure-vscode-keybindings.sh"
fi

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

if [[ "${SKIP_AUDIO_TWEAKS:-}" == "1" ]]; then
  log_step "Skipping audio defaults (SKIP_AUDIO_TWEAKS=1)"
else
  log_step "Applying audio defaults"
  "$ROOT_DIR/scripts/configure-audio.sh"
fi

if [[ "${SKIP_PTRACE_SCOPE:-}" == "1" ]]; then
  log_step "Skipping ptrace scope setup (SKIP_PTRACE_SCOPE=1)"
else
  log_step "Configuring ptrace scope for debugger attach"
  "$ROOT_DIR/scripts/configure-ptrace.sh"
fi

if [[ "${SKIP_GDB_PRETTY_PRINTERS:-}" == "1" ]]; then
  log_step "Skipping GDB pretty-printer setup (SKIP_GDB_PRETTY_PRINTERS=1)"
else
  log_step "Configuring GDB pretty printers"
  "$ROOT_DIR/scripts/configure-gdb-pretty-printers.sh"
fi

if command -v systemctl >/dev/null 2>&1; then
  log_step "Enabling Bluetooth service"
  "$ROOT_DIR/scripts/enable-bluetooth.sh"

  if [[ "${SKIP_GDM_MONITORS:-}" == "1" ]]; then
    log_step "Skipping GDM monitor sync setup (SKIP_GDM_MONITORS=1)"
  else
    log_step "Setting up GDM monitor sync"
    bash "$ROOT_DIR/scripts/setup-gdm-monitor-sync.sh"
  fi
else
  log_step "systemctl not available; skipping Bluetooth and GDM service setup"
fi

if [[ "${SKIP_SHELL:-}" == "1" ]]; then
  log_step "Skipping default shell change (SKIP_SHELL=1)"
else
  log_step "Setting default shell to fish"
  "$ROOT_DIR/scripts/set-default-shell.sh"
fi

if [[ "${SKIP_GNOME_EXTENSIONS:-}" == "1" ]]; then
  log_step "Skipping GNOME extension setup (SKIP_GNOME_EXTENSIONS=1)"
else
  if command -v gnome-extensions >/dev/null 2>&1; then
    log_step "Enabling GNOME extensions"
    "$ROOT_DIR/scripts/enable-gnome-extensions.sh"
  else
    log_step "gnome-extensions not available; skipping"
  fi

  log_step "Configuring Arch Update Indicator defaults"
  "$ROOT_DIR/scripts/configure-gnome-arch-update.sh"
fi
