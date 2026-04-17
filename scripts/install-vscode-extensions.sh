#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=./logging.sh
source "$SCRIPT_DIR/logging.sh"

EXTENSION_LIST="${1:-$SCRIPT_DIR/../packages/vscode.extensions}"

if [[ ! -f "$EXTENSION_LIST" ]]; then
  echo "VS Code extension list not found: $EXTENSION_LIST" >&2
  exit 1
fi

mapfile -t extensions < <(grep -v '^#' "$EXTENSION_LIST" | grep -v '^$')

if (( ${#extensions[@]} == 0 )); then
  log_step "No VS Code extensions listed in $EXTENSION_LIST; skipping"
  exit 0
fi

if ! command -v code >/dev/null 2>&1; then
  log_step "VS Code CLI ('code') not found; skipping extension install"
  exit 0
fi

installed_extensions=""
if ! installed_extensions=$(code --list-extensions 2>/dev/null); then
  log_step "Could not list installed VS Code extensions; proceeding with requested installs"
fi

missing_extensions=()
for extension in "${extensions[@]}"; do
  if ! grep -Fxq "$extension" <<<"$installed_extensions"; then
    missing_extensions+=("$extension")
  fi
done

if (( ${#missing_extensions[@]} == 0 )); then
  log_step "All ${#extensions[@]} VS Code extensions already installed; skipping"
  exit 0
fi

log_step "Installing ${#missing_extensions[@]} missing VS Code extensions from $EXTENSION_LIST"
for extension in "${missing_extensions[@]}"; do
  code --install-extension "$extension"
done
