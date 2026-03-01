#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
ROOT_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
# shellcheck source=./logging.sh
source "$SCRIPT_DIR/logging.sh"

log_step "Applying config files"
# Copy ~/.config files
if [[ -d "$ROOT_DIR/config" ]]; then
  mkdir -p "$HOME/.config"
  cp -R "$ROOT_DIR/config/"* "$HOME/.config/" 2>/dev/null || true
fi

log_step "Ensuring fish config directory exists"
# Ensure fish config directory exists
mkdir -p "$HOME/.config/fish"
