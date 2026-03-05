#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=./logging.sh
source "$SCRIPT_DIR/logging.sh"

PACKAGE_LIST="${1:-$(dirname "$0")/../packages/base.packages}"

if [[ ! -f "$PACKAGE_LIST" ]]; then
  echo "Package list not found: $PACKAGE_LIST" >&2
  exit 1
fi

mapfile -t packages < <(grep -v '^#' "$PACKAGE_LIST" | grep -v '^$')

if (( ${#packages[@]} == 0 )); then
  echo "No packages found in $PACKAGE_LIST" >&2
  exit 1
fi

missing_packages=()
for pkg in "${packages[@]}"; do
  if ! pacman -Q "$pkg" >/dev/null 2>&1; then
    missing_packages+=("$pkg")
  fi
done

if (( ${#missing_packages[@]} == 0 )); then
  log_step "All ${#packages[@]} packages already installed; skipping"
  exit 0
fi

log_step "Installing ${#missing_packages[@]} missing packages from $PACKAGE_LIST"
sudo pacman -S --noconfirm --needed "${missing_packages[@]}"
