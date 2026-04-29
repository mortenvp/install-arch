#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=./logging.sh
source "$SCRIPT_DIR/logging.sh"

log_step "Installing base packages"
"$SCRIPT_DIR/install-packages.sh" "$SCRIPT_DIR/../packages/base.packages"

log_step "Installing Warp terminal"
"$SCRIPT_DIR/install-warp-terminal.sh"

log_step "Installing AUR packages"
"$SCRIPT_DIR/install-aur-packages.sh" "$SCRIPT_DIR/../packages/aur.packages"

log_step "Installing upstream tools"
"$SCRIPT_DIR/install-upstream-tools.sh"
