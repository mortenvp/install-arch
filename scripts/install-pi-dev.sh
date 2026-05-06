#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=./logging.sh
source "$SCRIPT_DIR/logging.sh"

PACKAGE="@mariozechner/pi-coding-agent"

if ! command -v npm >/dev/null 2>&1; then
  log_step "npm not found; installing npm"
  sudo pacman -S --noconfirm --needed npm
fi

if npm list -g --depth=0 "$PACKAGE" >/dev/null 2>&1; then
  log_step "$PACKAGE already installed globally; skipping"
  exit 0
fi

log_step "Installing $PACKAGE globally via npm"
sudo npm install -g "$PACKAGE"
