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

log_step "Installing ${#packages[@]} packages from $PACKAGE_LIST"
sudo pacman -S --noconfirm --needed "${packages[@]}"
