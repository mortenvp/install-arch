#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VAGRANT_DIR="${SCRIPT_DIR}/vagrant"
BOOTSTRAP_URL="${BOOTSTRAP_URL:-https://raw.githubusercontent.com/mortenvp/install-arch/main/boot.sh}"
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
vagrant ssh -c "bash -lc 'export TERM=xterm; if command -v curl >/dev/null 2>&1; then curl -fsSL ${BOOTSTRAP_URL} | bash; elif command -v wget >/dev/null 2>&1; then wget -qO- ${BOOTSTRAP_URL} | bash; else echo \"Neither curl nor wget is installed in the VM.\" >&2; exit 1; fi'"

echo "Install test completed successfully."
