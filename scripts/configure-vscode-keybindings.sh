#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=./logging.sh
source "$SCRIPT_DIR/logging.sh"

VSCODE_KEYBINDINGS_TARGET="$HOME/.config/Code/User/keybindings.json"

if ! command -v code >/dev/null 2>&1; then
  log_step "VS Code CLI ('code') not found; skipping keybinding setup"
  exit 0
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required to configure VS Code keybindings. Install jq and retry." >&2
  exit 1
fi

mkdir -p "$(dirname "$VSCODE_KEYBINDINGS_TARGET")"

if [[ ! -f "$VSCODE_KEYBINDINGS_TARGET" ]]; then
  printf '[]\n' >"$VSCODE_KEYBINDINGS_TARGET"
fi

if ! jq -e 'type == "array"' "$VSCODE_KEYBINDINGS_TARGET" >/dev/null 2>&1; then
  echo "Invalid VS Code keybindings JSON at $VSCODE_KEYBINDINGS_TARGET (expected array)." >&2
  exit 1
fi

keybindings_tmp=$(mktemp)

jq '
  map(select((.key // "") != "alt+q" and (.linux // "") != "alt+q"))
  + [
      {
        key: "alt+q",
        command: "rewrap.rewrapComment",
        when: "editorTextFocus"
      }
    ]
' "$VSCODE_KEYBINDINGS_TARGET" >"$keybindings_tmp"

install -m 644 "$keybindings_tmp" "$VSCODE_KEYBINDINGS_TARGET"
rm -f "$keybindings_tmp"

log_step "Bound Alt+Q to Rewrap Revived in $VSCODE_KEYBINDINGS_TARGET"
