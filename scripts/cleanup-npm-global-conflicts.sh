#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=./logging.sh
source "$SCRIPT_DIR/logging.sh"

# Top-level paths that often conflict when previously installed via `npm -g` with sudo.
EXACT_PATHS=(
  /usr/bin/pn
  /usr/bin/pnx
)

NODE_MODULE_TREES=(
  /usr/lib/node_modules/pnpm
  /usr/lib/node_modules/typescript
)

removed=0

remove_unowned_path() {
  local path="$1"
  [[ -e "$path" || -L "$path" ]] || return 0

  if pacman -Qo "$path" >/dev/null 2>&1; then
    return 0
  fi

  if (( removed == 0 )); then
    log_step "Removing unowned npm-global paths under /usr that conflict with pacman"
  fi

  sudo rm -rf "$path"
  echo "removed: $path"
  removed=1
}

for path in "${EXACT_PATHS[@]}"; do
  remove_unowned_path "$path"
done

for tree in "${NODE_MODULE_TREES[@]}"; do
  [[ -d "$tree" ]] || continue

  # Remove unowned files even inside pacman-owned directories. These are what
  # typically cause "exists in filesystem" conflicts during upgrades.
  while IFS= read -r path; do
    remove_unowned_path "$path"
  done < <(find "$tree" -mindepth 1 -depth 2>/dev/null)

  # If the top directory itself is unowned and now empty, remove it too.
  if [[ -d "$tree" ]] && ! pacman -Qo "$tree" >/dev/null 2>&1; then
    if [[ -z "$(find "$tree" -mindepth 1 -print -quit 2>/dev/null)" ]]; then
      remove_unowned_path "$tree"
    fi
  fi
done

if (( removed == 0 )); then
  log_step "No unowned conflicting npm-global paths found"
fi
