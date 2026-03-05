#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
ROOT_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
# shellcheck source=./logging.sh
source "$SCRIPT_DIR/logging.sh"

log_step "Applying config files"
VSCODE_SETTINGS_SRC="$ROOT_DIR/config/Code/User/settings.json"
VSCODE_SETTINGS_TARGET="$HOME/.config/Code/User/settings.json"
VSCODE_SETTINGS_BACKUP=""

if [[ -f "$VSCODE_SETTINGS_TARGET" ]]; then
  VSCODE_SETTINGS_BACKUP=$(mktemp)
  cp "$VSCODE_SETTINGS_TARGET" "$VSCODE_SETTINGS_BACKUP"
fi

# Copy ~/.config files
if [[ -d "$ROOT_DIR/config" ]]; then
  mkdir -p "$HOME/.config"
  cp -R "$ROOT_DIR/config/"* "$HOME/.config/" 2>/dev/null || true
fi

if [[ -n "$VSCODE_SETTINGS_BACKUP" ]]; then
  mkdir -p "$(dirname "$VSCODE_SETTINGS_TARGET")"
  cp "$VSCODE_SETTINGS_BACKUP" "$VSCODE_SETTINGS_TARGET"
  rm -f "$VSCODE_SETTINGS_BACKUP"
  log_step "VS Code settings already exist at $VSCODE_SETTINGS_TARGET; skipping"
elif [[ -f "$VSCODE_SETTINGS_SRC" ]]; then
  log_step "Applied VS Code settings defaults to $VSCODE_SETTINGS_TARGET"
fi

log_step "Ensuring fish config directory exists"
# Ensure fish config directory exists
mkdir -p "$HOME/.config/fish"
