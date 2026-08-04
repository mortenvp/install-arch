#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=scripts/logging.sh
source "$SCRIPT_DIR/logging.sh"

MODE="install"
if [[ "${1:-}" == "--check" ]]; then
  MODE="check"
elif [[ $# -gt 0 ]]; then
  echo "Usage: $0 [--check]" >&2
  exit 1
fi

lix_present=0

nix_version=""
if command -v nix >/dev/null 2>&1; then
  nix_version=$(nix --version 2>/dev/null || true)
  if printf '%s\n' "$nix_version" | grep -qi 'lix'; then
    lix_present=1
  fi
fi

lix_packages=()
for pkg in lix lix-nix; do
  if pacman -Q "$pkg" >/dev/null 2>&1; then
    lix_packages+=("$pkg")
    lix_present=1
  fi
done

installer=""
for candidate in /nix/nix-installer /nix/lix-installer; do
  if [[ -x "$candidate" ]]; then
    installer="$candidate"
    lix_present=1
    break
  fi
done

if [[ -d /nix && ! -e /nix/var/nix/profiles/default/bin/nix && ${#lix_packages[@]} -eq 0 && -z "$installer" && "$lix_present" -eq 0 ]]; then
  log_step "/nix exists, but no Lix install was detected"
fi

if [[ "$MODE" == "check" ]]; then
  if [[ "$lix_present" -eq 1 ]]; then
    log_step "Lix detected; install mode would uninstall it"
    [[ -n "$nix_version" ]] && log_step "Detected nix version: $nix_version"
    (( ${#lix_packages[@]} > 0 )) && log_step "Detected pacman package(s): ${lix_packages[*]}"
    [[ -n "$installer" ]] && log_step "Detected upstream installer: $installer"
  else
    log_step "Lix not detected"
  fi
  exit 0
fi

if [[ "$lix_present" -eq 0 ]]; then
  log_step "Lix not detected; skipping removal"
  exit 0
fi

if command -v systemctl >/dev/null 2>&1 && [[ -d /run/systemd/system ]]; then
  if systemctl list-unit-files nix-daemon.service >/dev/null 2>&1; then
    log_step "Stopping nix-daemon.service before Lix removal"
    sudo systemctl stop nix-daemon.service 2>/dev/null || true
  fi
fi

if [[ -n "$installer" ]]; then
  log_step "Uninstalling Lix via $installer"
  if ! sudo "$installer" uninstall --no-confirm; then
    yes | sudo "$installer" uninstall
  fi
fi

if (( ${#lix_packages[@]} > 0 )); then
  log_step "Removing Lix pacman package(s): ${lix_packages[*]}"
  sudo pacman -Rns --noconfirm "${lix_packages[@]}"
fi

log_step "Lix removal complete"
