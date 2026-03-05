#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=./logging.sh
source "$SCRIPT_DIR/logging.sh"

if command -v devbox >/dev/null 2>&1; then
  log_step "devbox already installed; skipping upstream installer"
  exit 0
fi

log_step "Installing devbox via upstream installer"
curl -fsSL https://get.jetify.com/devbox | bash -s -- -f
