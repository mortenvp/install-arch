#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VAGRANT_DIR="${SCRIPT_DIR}/vagrant"
BOOTSTRAP_URL="https://raw.githubusercontent.com/mortenvp/install-arch/main/boot.sh"
export VAGRANT_HOME="${VAGRANT_HOME:-${VAGRANT_DIR}/.vagrant.d}"

cleanup() {
  echo "Destroying VM instance..."
  (
    cd "${VAGRANT_DIR}"
    vagrant destroy -f >/dev/null 2>&1 || true
  )
}

trap cleanup EXIT

cd "${VAGRANT_DIR}"

echo "Ensuring clean VM instance..."
vagrant destroy -f || true

echo "Booting VM..."
vagrant up --provider=virtualbox

echo "Running install from ${BOOTSTRAP_URL}..."
vagrant ssh -c "bash -lc 'export TERM=xterm; sudo pacman-key --init; sudo pacman-key --populate archlinux; sudo pacman -Sy --noconfirm archlinux-keyring; command -v curl >/dev/null || sudo pacman -Sy --noconfirm curl; curl -fsSL ${BOOTSTRAP_URL} | bash'"

echo "Install test completed successfully."
