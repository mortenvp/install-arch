#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=scripts/logging.sh
source "$SCRIPT_DIR/logging.sh"

SYSCTL_KEY="kernel.perf_event_paranoid"
SYSCTL_VALUE="1"
SYSCTL_FILE="/etc/sysctl.d/10-perf-events.conf"

if ! command -v sysctl >/dev/null 2>&1; then
  log_step "sysctl not available; skipping perf event setup"
  exit 0
fi

if [[ ! -r /proc/sys/kernel/perf_event_paranoid ]]; then
  log_step "${SYSCTL_KEY} is unavailable; skipping perf event setup"
  exit 0
fi

log_step "Setting ${SYSCTL_KEY}=${SYSCTL_VALUE}"
sudo install -d -m 755 /etc/sysctl.d
sudo tee "$SYSCTL_FILE" >/dev/null <<EOF
${SYSCTL_KEY} = ${SYSCTL_VALUE}
EOF

sudo sysctl -w "${SYSCTL_KEY}=${SYSCTL_VALUE}" >/dev/null
log_step "Applied ${SYSCTL_KEY}=${SYSCTL_VALUE} and persisted in ${SYSCTL_FILE}"
