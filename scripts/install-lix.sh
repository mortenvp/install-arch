#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=./logging.sh
source "$SCRIPT_DIR/logging.sh"

if command -v nix >/dev/null 2>&1; then
  log_step "nix already installed; skipping Lix installer"
  exit 0
fi

log_step "Installing Lix (nix) via upstream installer"
curl -sSf -L https://install.lix.systems/lix | sh -s -- install --no-confirm
