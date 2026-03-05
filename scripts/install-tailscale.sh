#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=./logging.sh
source "$SCRIPT_DIR/logging.sh"

if command -v tailscale >/dev/null 2>&1; then
  log_step "tailscale already installed; skipping upstream installer"
  exit 0
fi

log_step "Installing tailscale via upstream installer"
curl -fsSL https://tailscale.com/install.sh | sh
