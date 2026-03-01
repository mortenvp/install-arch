#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=./logging.sh
source "$SCRIPT_DIR/logging.sh"

SHELL_PATH="/usr/bin/fish"

if ! command -v fish >/dev/null 2>&1; then
  echo "fish is not installed. Install it first." >&2
  exit 1
fi

if ! grep -q "^${SHELL_PATH}$" /etc/shells; then
  echo "${SHELL_PATH} is not in /etc/shells. You may need sudo to add it." >&2
  exit 1
fi

log_step "Setting default shell to $SHELL_PATH"
chsh -s "$SHELL_PATH"
echo "Default shell set to fish. Log out and back in to apply."
