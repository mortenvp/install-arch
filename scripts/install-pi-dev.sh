#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=./logging.sh
source "$SCRIPT_DIR/logging.sh"

PACKAGE="@earendil-works/pi-coding-agent"
OLD_PACKAGE="@mariozechner/pi-coding-agent"

"$SCRIPT_DIR/ensure-user-npm-global.sh"

if npm list -g --depth=0 "$OLD_PACKAGE" >/dev/null 2>&1; then
  log_step "Removing legacy package $OLD_PACKAGE"
  npm uninstall -g "$OLD_PACKAGE"
fi

if npm list -g --depth=0 "$PACKAGE" >/dev/null 2>&1; then
  log_step "$PACKAGE already installed globally; skipping"
  exit 0
fi

log_step "Installing $PACKAGE globally via npm (user-local)"
npm install -g "$PACKAGE"
