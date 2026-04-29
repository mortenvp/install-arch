#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=./logging.sh
source "$SCRIPT_DIR/logging.sh"

PACMAN_CONF="/etc/pacman.conf"
WARP_SIGNING_KEY="linux-maintainers@warp.dev"

if ! command -v pacman >/dev/null 2>&1; then
  log_step "pacman not available; skipping Warp terminal setup"
  exit 0
fi

if ! grep -Eq '^[[:space:]]*\[warpdotdev\][[:space:]]*$' "$PACMAN_CONF"; then
  log_step "Adding Warp pacman repository to $PACMAN_CONF"
  sudo tee -a "$PACMAN_CONF" >/dev/null <<'EOF'

[warpdotdev]
Server = https://releases.warp.dev/linux/pacman/$repo/$arch
EOF
else
  log_step "Warp pacman repository already configured"
fi

if ! sudo pacman-key --list-keys "$WARP_SIGNING_KEY" >/dev/null 2>&1; then
  log_step "Importing Warp package signing key"
  sudo pacman-key -r "$WARP_SIGNING_KEY"
else
  log_step "Warp signing key already present"
fi

log_step "Locally signing Warp package key"
sudo pacman-key --lsign-key "$WARP_SIGNING_KEY"

mapfile -t installed_warp_candidates < <(pacman -Qq warp-terminal 2>/dev/null || true)
for pkg in "${installed_warp_candidates[@]}"; do
  if [[ "$pkg" == "warp-terminal" ]]; then
    continue
  fi

  pkg_info=$(pacman -Qi "$pkg" 2>/dev/null || true)
  if [[ "$pkg_info" == *"Provides        : "*warp-terminal* ]]; then
    log_step "Removing conflicting package $pkg before installing official warp-terminal"
    sudo pacman -R --noconfirm "$pkg"
  fi
done

log_step "Installing Warp terminal from Warp pacman repository"
sudo pacman -Sy --noconfirm --needed warp-terminal
