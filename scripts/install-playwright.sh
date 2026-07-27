#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=scripts/logging.sh
source "$SCRIPT_DIR/logging.sh"

"$SCRIPT_DIR/ensure-user-npm-global.sh"

USER_NPM_PREFIX="${USER_NPM_PREFIX:-$HOME/.local}"
export NPM_CONFIG_PREFIX="$USER_NPM_PREFIX"
export PATH="$USER_NPM_PREFIX/bin:$PATH"

if npm list -g --depth=0 playwright >/dev/null 2>&1; then
  log_step "playwright already installed globally; skipping npm install"
else
  log_step "Installing playwright globally via npm (user-local)"
  npm install -g playwright
fi

log_step "Installing Playwright browsers"
npx playwright install
