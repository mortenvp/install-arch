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

if ! command -v nix >/dev/null 2>&1; then
  if [[ "$MODE" == "check" ]]; then
    log_step "nix is not installed"
    exit 1
  fi
  log_step "nix is not installed; skipping Nix service setup"
  exit 0
fi

nix_version=$(nix --version 2>/dev/null || true)
if printf '%s\n' "$nix_version" | grep -qi 'lix'; then
  if [[ "$MODE" == "check" ]]; then
    log_step "Lix is still active: $nix_version"
    exit 1
  fi
  log_step "Lix is still active; run scripts/remove-lix.sh before configuring Arch Nix"
  exit 1
fi

install_user=${SUDO_USER:-${USER:-}}
if [[ -z "$install_user" ]]; then
  install_user=$(id -un)
fi

if getent group nix-users >/dev/null 2>&1; then
  if id -nG "$install_user" | grep -qw 'nix-users'; then
    log_step "$install_user is already in nix-users"
  elif [[ "$MODE" == "check" ]]; then
    log_step "$install_user is not in nix-users"
    exit 1
  else
    log_step "Adding $install_user to nix-users"
    sudo usermod -aG nix-users "$install_user"
    log_step "$install_user may need to log out and back in before using nix"
  fi
else
  log_step "nix-users group not found; skipping user group setup"
fi

if ! command -v systemctl >/dev/null 2>&1; then
  log_step "systemctl not available; skipping Nix service setup"
  exit 0
fi

if [[ ! -d /run/systemd/system ]]; then
  log_step "systemd is not PID 1; skipping Nix service setup"
  exit 0
fi

log_step "Configuring nix-daemon.service"
if [[ ! -e /usr/lib/systemd/system/nix-daemon.service && ! -e /etc/systemd/system/nix-daemon.service ]]; then
  if [[ "$MODE" == "check" ]]; then
    log_step "nix-daemon.service unit not found"
    exit 1
  fi
  log_step "nix-daemon.service unit not found; skipping"
  exit 0
fi

is_enabled="$(systemctl is-enabled nix-daemon.service 2>/dev/null || true)"
is_active="$(systemctl is-active nix-daemon.service 2>/dev/null || true)"

if [[ "$MODE" == "check" ]]; then
  log_step "nix version: $nix_version"
  log_step "nix-daemon.service enabled: $is_enabled"
  log_step "nix-daemon.service active: $is_active"
  [[ "$is_enabled" == "enabled" && "$is_active" == "active" ]]
  exit $?
fi

if [[ "$is_enabled" == "enabled" && "$is_active" == "active" ]]; then
  log_step "nix-daemon.service already enabled and active; skipping"
  exit 0
fi

sudo systemctl enable --now nix-daemon.service
