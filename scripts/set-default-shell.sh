#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=./logging.sh
source "$SCRIPT_DIR/logging.sh"

SHELL_PATH="/usr/bin/fish"
TARGET_USER="${SUDO_USER:-${USER:-}}"

if ! command -v fish >/dev/null 2>&1; then
  echo "fish is not installed. Install it first." >&2
  exit 1
fi

if ! grep -q "^${SHELL_PATH}$" /etc/shells; then
  echo "${SHELL_PATH} is not in /etc/shells. You may need sudo to add it." >&2
  exit 1
fi

if [[ -z "$TARGET_USER" ]]; then
  echo "Could not determine target user for shell change." >&2
  exit 1
fi

current_shell=$(getent passwd "$TARGET_USER" | awk -F: '{print $7}')
if [[ "$current_shell" == "$SHELL_PATH" ]]; then
  log_step "Default shell already set to $SHELL_PATH for $TARGET_USER; skipping"
  exit 0
fi

log_step "Setting default shell to $SHELL_PATH for $TARGET_USER"
sudo usermod --shell "$SHELL_PATH" "$TARGET_USER"

current_shell=$(getent passwd "$TARGET_USER" | awk -F: '{print $7}')
if [[ "$current_shell" != "$SHELL_PATH" ]]; then
  echo "Shell change verification failed for $TARGET_USER." >&2
  exit 1
fi

echo "Default shell set to fish for $TARGET_USER. Log out and back in to apply."
