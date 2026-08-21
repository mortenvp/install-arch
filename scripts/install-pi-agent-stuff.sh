#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=scripts/logging.sh
source "$SCRIPT_DIR/logging.sh"

PACKAGE_SOURCE="git:github.com/mortenvp/agent-stuff@main"

if ! command -v pi >/dev/null 2>&1; then
  log_step "pi is not installed; skipping personal Pi package"
  exit 0
fi

log_step "Installing personal Pi package from $PACKAGE_SOURCE"
pi install "$PACKAGE_SOURCE"
