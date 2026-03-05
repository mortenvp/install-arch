#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=./logging.sh
source "$SCRIPT_DIR/logging.sh"

PACKAGE_LIST="${1:-$(dirname "$0")/../packages/aur.packages}"

if [[ ! -f "$PACKAGE_LIST" ]]; then
  echo "Package list not found: $PACKAGE_LIST" >&2
  exit 1
fi

ensure_yay() {
  if command -v yay >/dev/null 2>&1; then
    return 0
  fi

  log_step "Installing yay-bin (AUR helper)"
  sudo pacman -S --noconfirm --needed base-devel git

  local tmp_dir
  tmp_dir="$(mktemp -d)"
  trap 'rm -rf "$tmp_dir"' RETURN

  git clone https://aur.archlinux.org/yay-bin.git "$tmp_dir/yay-bin"
  (
    cd "$tmp_dir/yay-bin"
    makepkg -si --noconfirm
  )

  if ! command -v yay >/dev/null 2>&1; then
    echo "Failed to install yay from yay-bin." >&2
    exit 1
  fi
}

ensure_yay

mapfile -t packages < <(grep -v '^#' "$PACKAGE_LIST" | grep -v '^$')

if (( ${#packages[@]} == 0 )); then
  echo "No packages found in $PACKAGE_LIST" >&2
  exit 1
fi

log_step "Installing ${#packages[@]} AUR packages from $PACKAGE_LIST"
yay -S --noconfirm --needed "${packages[@]}"
