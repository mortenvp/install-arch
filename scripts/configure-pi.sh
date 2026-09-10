#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
ROOT_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
# shellcheck source=scripts/logging.sh
source "$SCRIPT_DIR/logging.sh"

SETTINGS_SRC="$ROOT_DIR/config/pi/settings.json"
SETTINGS_DIR="${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}"
SETTINGS_TARGET="$SETTINGS_DIR/settings.json"

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required to configure Pi. Install jq and retry." >&2
  exit 1
fi

settings_input=/dev/null
if [[ -e "$SETTINGS_TARGET" ]]; then
  if ! jq -se 'length == 1 and (.[0] | type == "object")' "$SETTINGS_TARGET" >/dev/null 2>&1; then
    echo "Invalid Pi settings JSON at $SETTINGS_TARGET (expected object); leaving it unchanged." >&2
    exit 1
  fi
  settings_input="$SETTINGS_TARGET"
fi

mkdir -p "$SETTINGS_DIR"
settings_tmp=$(mktemp "$SETTINGS_DIR/.settings.json.XXXXXX")
trap 'rm -f "$settings_tmp"' EXIT

# Recursively merge managed defaults while preserving unrelated Pi settings.
jq -s --slurpfile defaults "$SETTINGS_SRC" \
  '(.[0] // {}) * $defaults[0]' "$settings_input" >"$settings_tmp"
chmod 600 "$settings_tmp"

if [[ -f "$SETTINGS_TARGET" ]] && cmp -s "$settings_tmp" "$SETTINGS_TARGET"; then
  log_step "Pi settings already up to date"
else
  mv "$settings_tmp" "$SETTINGS_TARGET"
  log_step "Configured Pi to use openai-codex/gpt-6-astra with xhigh thinking in $SETTINGS_TARGET"
fi
