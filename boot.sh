#!/usr/bin/env bash
set -euo pipefail

# Online install entry point (curl | bash)
read -r -d '' ansi_art <<'EOF' || true
   ___           __        __        ___             __
  / _ \___ ______/ /____ __/ /__ ____/ _ | _________ / /_
 / ___/ _ `/ __/ _  / -_) _  / -_) __/ __ |/ __/ __/  \/
/_/   \_,_/_/  \_,_/\__/\_,_/\__/_/ /_/ |_/_/  \__/_/\_\
EOF

export TERM="${TERM:-xterm}"
clear
printf "\n%s\n" "$ansi_art"

printf "\nPreparing pacman keyring...\n"
sudo pacman-key --init
sudo pacman-key --populate archlinux
sudo pacman -Sy --noconfirm archlinux-keyring

printf "\nInstalling bootstrap tools...\n"
sudo pacman -Syu --noconfirm --needed git

# Default repo and install dir
INSTALL_ARCH_REPO="${INSTALL_ARCH_REPO:-mortenvp/install-arch}"
INSTALL_ARCH_DIR="${INSTALL_ARCH_DIR:-$HOME/.local/share/install-arch}"

printf "\nCloning from: https://github.com/%s.git\n" "$INSTALL_ARCH_REPO"
rm -rf "$INSTALL_ARCH_DIR"
git clone "https://github.com/${INSTALL_ARCH_REPO}.git" "$INSTALL_ARCH_DIR" >/dev/null

INSTALL_ARCH_REF="${INSTALL_ARCH_REF:-main}"
printf "\nUsing branch: %s\n" "$INSTALL_ARCH_REF"
(
  cd "$INSTALL_ARCH_DIR"
  git fetch origin "$INSTALL_ARCH_REF" >/dev/null
  git checkout "$INSTALL_ARCH_REF" >/dev/null
)

printf "\nInstallation starting...\n"
"$INSTALL_ARCH_DIR/install.sh"
