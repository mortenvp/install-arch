#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=./logging.sh
source "$SCRIPT_DIR/logging.sh"

if ! command -v npm >/dev/null 2>&1; then
  log_step "npm not found; installing npm"
  sudo pacman -S --noconfirm --needed npm
fi

if npm list -g --depth=0 playwright >/dev/null 2>&1; then
  log_step "playwright already installed globally; skipping npm install"
else
  log_step "Installing playwright globally via npm"
  sudo npm install -g playwright
fi

log_step "Installing Playwright browsers"
npx playwright install
