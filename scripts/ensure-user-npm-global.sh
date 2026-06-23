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

USER_NPM_PREFIX="$HOME/.local"
CURRENT_PREFIX="$(npm config get prefix 2>/dev/null || true)"

if [[ "$CURRENT_PREFIX" != "$USER_NPM_PREFIX" ]]; then
  log_step "Configuring npm global prefix to $USER_NPM_PREFIX"
  npm config set prefix "$USER_NPM_PREFIX"
fi

export PATH="$USER_NPM_PREFIX/bin:$PATH"
