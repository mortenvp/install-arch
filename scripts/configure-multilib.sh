#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=scripts/logging.sh
source "$SCRIPT_DIR/logging.sh"

PACMAN_CONF="/etc/pacman.conf"
MIRRORLIST="/etc/pacman.d/mirrorlist"

# Resolve includes too, so an existing custom multilib repository is preserved.
repositories=$(pacman-conf --repo-list)
if grep -Fxq multilib <<<"$repositories"; then
  log_step "Arch multilib repository already enabled"
  exit 0
fi

if [[ ! -r "$MIRRORLIST" ]]; then
  echo "Mirror list not found: $MIRRORLIST; configure Arch mirrors first." >&2
  exit 1
fi

log_step "Enabling Arch multilib repository in $PACMAN_CONF"
if [[ ! -e "$PACMAN_CONF.before-steam" ]]; then
  sudo cp -p "$PACMAN_CONF" "$PACMAN_CONF.before-steam"
fi

# Leave commented examples and unrelated settings untouched.
sudo tee -a "$PACMAN_CONF" >/dev/null <<EOF

# Enabled by install-arch for Steam.
[multilib]
Include = $MIRRORLIST
EOF
