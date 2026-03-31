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
GIT_CONFIG_TARGET="$HOME/.config/git/config"
EXISTING_GIT_NAME=""
EXISTING_GIT_EMAIL=""

if command -v git >/dev/null 2>&1; then
  EXISTING_GIT_NAME=$(git config --global --get user.name || true)
  EXISTING_GIT_EMAIL=$(git config --global --get user.email || true)
fi

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

if [[ -n "$EXISTING_GIT_NAME" || -n "$EXISTING_GIT_EMAIL" ]]; then
  mkdir -p "$(dirname "$GIT_CONFIG_TARGET")"
  if [[ -n "$EXISTING_GIT_NAME" ]]; then
    git config --file "$GIT_CONFIG_TARGET" user.name "$EXISTING_GIT_NAME"
  fi
  if [[ -n "$EXISTING_GIT_EMAIL" ]]; then
    git config --file "$GIT_CONFIG_TARGET" user.email "$EXISTING_GIT_EMAIL"
  fi
  log_step "Preserved existing git user identity in $GIT_CONFIG_TARGET"
fi

log_step "Ensuring fish config directory exists"
# Ensure fish config directory exists
mkdir -p "$HOME/.config/fish"
