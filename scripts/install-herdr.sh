#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=scripts/logging.sh
source "$SCRIPT_DIR/logging.sh"

if [[ "${SKIP_HERDR:-}" == "1" ]]; then
  log_step "Skipping Herdr (SKIP_HERDR=1)"
  exit 0
fi

if [[ ${EUID:-$(id -u)} -eq 0 ]]; then
  echo "Please run this script as your regular user (not root/sudo)." >&2
  exit 1
fi

is_installed() {
  command -v "$1" >/dev/null 2>&1 || [[ -x "$HOME/.local/bin/$1" ]]
}

if is_installed herdr-app && is_installed herdr-core && is_installed herdr; then
  log_step "Herdr desktop, core, and terminal apps already installed; skipping official installers"
  exit 0
fi

required_packages=(curl gawk)
if ! is_installed herdr-app || ! is_installed herdr-core; then
  # libxkbcommon-x11 also pulls in the app's libxcb/libxkbcommon dependencies.
  # A working Vulkan driver is still required for the desktop app.
  required_packages+=(tar libxkbcommon-x11 vulkan-icd-loader)
fi
missing_packages=()
for package in "${required_packages[@]}"; do
  if ! pacman -Q "$package" >/dev/null 2>&1; then
    missing_packages+=("$package")
  fi
done
if (( ${#missing_packages[@]} > 0 )); then
  log_step "Installing Herdr dependencies"
  sudo pacman -S --noconfirm --needed "${missing_packages[@]}"
fi

TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

install_component() {
  local component="$1"
  local url="${2:-https://releases.herdr.dev/$component/install.sh}"
  local installer="$TEMP_DIR/$component.sh"
  # Download completely before executing; do not run partial failed downloads.
  curl -fsSL "$url" -o "$installer"
  sh "$installer"
}

# Install core first: the app's installer otherwise treats core failure as a warning.
if ! is_installed herdr-core; then
  log_step "Installing herdr-core via the official installer"
  HC_INSTALL_DIR="$HOME/.local/bin" install_component core
  if ! is_installed herdr-core; then
    echo "The Herdr core installer did not install herdr-core." >&2
    exit 1
  fi
fi

if ! is_installed herdr-app; then
  log_step "Installing Herdr via the official installer"
  install_component app
  if ! is_installed herdr-app; then
    echo "The Herdr app installer did not install herdr-app." >&2
    exit 1
  fi
fi

if ! is_installed herdr; then
  log_step "Installing the Herdr terminal app via the official installer"
  HERDR_INSTALL_DIR="$HOME/.local/bin" install_component terminal "https://herdr.dev/install.sh"
  if ! is_installed herdr; then
    echo "The Herdr terminal installer did not install herdr." >&2
    exit 1
  fi
fi

log_step "Herdr is ready. Run herdr in your terminal, or open the desktop app with herdr-app."
