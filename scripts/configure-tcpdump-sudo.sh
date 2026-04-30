#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=./logging.sh
source "$SCRIPT_DIR/logging.sh"

TARGET_USER="${SUDO_USER:-${USER:-$(id -un)}}"
TCPDUMP_PATH="/usr/bin/tcpdump"
SUDOERS_FILE="/etc/sudoers.d/10-tcpdump-${TARGET_USER}"

if [[ ! "$TARGET_USER" =~ ^[A-Za-z0-9_.-]+$ ]]; then
  log_step "Username '${TARGET_USER}' is not safe for sudoers; skipping tcpdump sudo setup"
  exit 0
fi

if ! id -u "$TARGET_USER" >/dev/null 2>&1; then
  log_step "User '${TARGET_USER}' does not exist; skipping tcpdump sudo setup"
  exit 0
fi

if ! command -v sudo >/dev/null 2>&1; then
  log_step "sudo not available; skipping tcpdump sudo setup"
  exit 0
fi

if ! command -v visudo >/dev/null 2>&1; then
  log_step "visudo not available; skipping tcpdump sudo setup"
  exit 0
fi

log_step "Allowing ${TARGET_USER} to run tcpdump with sudo without a password"

tmp_file="$(mktemp)"
trap 'rm -f "$tmp_file"' EXIT

cat >"$tmp_file" <<EOF
${TARGET_USER} ALL=(root) NOPASSWD: ${TCPDUMP_PATH}
EOF

sudo visudo -cf "$tmp_file" >/dev/null
sudo install -d -m 750 /etc/sudoers.d
sudo install -m 440 "$tmp_file" "$SUDOERS_FILE"
sudo visudo -cf "$SUDOERS_FILE" >/dev/null

log_step "Installed ${SUDOERS_FILE}"
