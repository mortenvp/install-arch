#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=scripts/logging.sh
source "$SCRIPT_DIR/logging.sh"

if ! command -v npm >/dev/null 2>&1; then
  log_step "npm not found; installing npm"
  sudo pacman -S --noconfirm --needed npm
elif ! npm --version >/dev/null 2>&1; then
  log_step "npm is installed but broken; reinstalling npm"
  sudo pacman -S --noconfirm npm
fi

USER_NPM_PREFIX="${USER_NPM_PREFIX:-$HOME/.local}"

# Do not persist npm's global prefix in ~/.npmrc: nvm-based AUR builds fail when
# user npm config contains prefix/globalconfig. Use NPM_CONFIG_PREFIX per command
# instead, and clean up any legacy settings this repo may have written before.
if [[ -f "$HOME/.npmrc" ]] && grep -Eq '^[[:space:]]*(prefix|globalconfig)[[:space:]]*=' "$HOME/.npmrc"; then
  log_step "Removing nvm-incompatible prefix/globalconfig from ~/.npmrc"
  sed -i.bak -E '/^[[:space:]]*(prefix|globalconfig)[[:space:]]*=/d' "$HOME/.npmrc"
fi

mkdir -p "$USER_NPM_PREFIX"
export NPM_CONFIG_PREFIX="$USER_NPM_PREFIX"
export PATH="$USER_NPM_PREFIX/bin:$PATH"
