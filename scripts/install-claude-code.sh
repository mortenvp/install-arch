#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=scripts/logging.sh
source "$SCRIPT_DIR/logging.sh"

if command -v claude >/dev/null 2>&1 || [[ -x "$HOME/.local/bin/claude" ]]; then
  log_step "Claude Code already installed; skipping official installer"
  exit 0
fi

log_step "Installing Claude Code via the official installer"
curl -fsSL https://claude.ai/install.sh | bash
