#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=./logging.sh
source "$SCRIPT_DIR/logging.sh"

SYSCTL_KEY="kernel.yama.ptrace_scope"
SYSCTL_VALUE="0"
SYSCTL_FILE="/etc/sysctl.d/10-ptrace.conf"

if ! command -v sysctl >/dev/null 2>&1; then
  log_step "sysctl not available; skipping ptrace scope setup"
  exit 0
fi

if [[ ! -r /proc/sys/kernel/yama/ptrace_scope ]]; then
  log_step "kernel.yama.ptrace_scope is unavailable; skipping ptrace scope setup"
  exit 0
fi

log_step "Setting ${SYSCTL_KEY}=${SYSCTL_VALUE} (reduces system security)"
sudo install -d -m 755 /etc/sysctl.d
sudo tee "$SYSCTL_FILE" >/dev/null <<EOF
${SYSCTL_KEY} = ${SYSCTL_VALUE}
EOF

sudo sysctl -w "${SYSCTL_KEY}=${SYSCTL_VALUE}" >/dev/null
log_step "Applied ${SYSCTL_KEY}=${SYSCTL_VALUE} and persisted in ${SYSCTL_FILE}"
