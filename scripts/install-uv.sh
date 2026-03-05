#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=./logging.sh
source "$SCRIPT_DIR/logging.sh"

if command -v uv >/dev/null 2>&1; then
  log_step "uv already installed; skipping upstream installer"
  exit 0
fi

log_step "Installing uv via upstream installer"
curl -fsSL https://astral.sh/uv/install.sh | sh
