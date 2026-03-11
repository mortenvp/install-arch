#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
PACKAGE_LIST="${1:-${ROOT_DIR}/packages/base.packages}"

if ! command -v pacman >/dev/null 2>&1; then
  echo "pacman not found; this script must run on Arch Linux." >&2
  exit 2
fi

if [[ ! -f "${PACKAGE_LIST}" ]]; then
  echo "Package list not found: ${PACKAGE_LIST}" >&2
  exit 1
fi

mapfile -t packages < <(grep -v '^[[:space:]]*#' "${PACKAGE_LIST}" | grep -v '^[[:space:]]*$')

if (( ${#packages[@]} == 0 )); then
  echo "No packages found in ${PACKAGE_LIST}" >&2
  exit 1
fi

missing_packages=()
for pkg in "${packages[@]}"; do
  if ! pacman -Si "${pkg}" >/dev/null 2>&1; then
    missing_packages+=("${pkg}")
  fi
done

total=${#packages[@]}
missing=${#missing_packages[@]}
valid=$((total - missing))

echo "Checked ${total} packages from ${PACKAGE_LIST}"
echo "Available in pacman: ${valid}"

if (( missing == 0 )); then
  echo "Missing from pacman: 0"
  echo "OK: all base packages are available via pacman"
  exit 0
fi

echo "Missing from pacman: ${missing}"
for pkg in "${missing_packages[@]}"; do
  echo "- ${pkg}"
done

exit 1
