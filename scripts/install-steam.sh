#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=scripts/logging.sh
source "$SCRIPT_DIR/logging.sh"

MODE="install"
if (( $# > 1 )) || [[ -n "${1:-}" && "${1:-}" != "--check" ]]; then
  echo "Usage: $0 [--check]" >&2
  exit 1
elif [[ "${1:-}" == "--check" ]]; then
  MODE="check"
fi

if [[ "${SKIP_STEAM:-}" == "1" ]]; then
  log_step "Skipping Steam (SKIP_STEAM=1)"
  exit 0
fi

if ! command -v pacman >/dev/null 2>&1 || ! command -v pacman-conf >/dev/null 2>&1; then
  echo "pacman not found; this script must run on Arch Linux." >&2
  exit 2
fi

if [[ "$(uname -m)" != "x86_64" ]]; then
  echo "Arch's Steam package requires x86_64." >&2
  exit 2
fi

has_intel=false
has_amd=false
has_nvidia=false

# PCI discovery also sees GPUs without a loaded driver, including hybrid laptops.
for device in /sys/bus/pci/devices/*; do
  [[ -r "$device/class" && -r "$device/vendor" ]] || continue
  [[ "$(<"$device/class")" == 0x03* ]] || continue
  case "$(<"$device/vendor")" in
    0x8086) has_intel=true ;;
    0x1002) has_amd=true ;;
    0x10de) has_nvidia=true ;;
  esac
done

# Select explicit Vulkan providers: pacman's noninteractive default may otherwise
# install a driver for the wrong GPU. Steam and Proton need 32-bit libraries too.
packages=(steam mesa lib32-mesa vulkan-icd-loader lib32-vulkan-icd-loader)
if $has_intel; then
  packages+=(vulkan-intel lib32-vulkan-intel)
fi
if $has_amd; then
  packages+=(vulkan-radeon lib32-vulkan-radeon)
fi
if $has_nvidia; then
  packages+=(nvidia-utils lib32-nvidia-utils)
fi
if ! $has_intel && ! $has_amd && ! $has_nvidia; then
  log_step "No supported GPU detected; using software Vulkan (limited gaming performance)"
  packages+=(vulkan-swrast lib32-vulkan-swrast)
fi

log_step "Steam packages: ${packages[*]}"
if [[ "$MODE" == "check" ]]; then
  log_step "Check mode enabled; not enabling multilib or installing packages"
  exit 0
fi

"$SCRIPT_DIR/configure-multilib.sh"

# Refresh newly enabled multilib with a full upgrade, never a partial -Sy upgrade.
log_step "Installing Steam and GPU libraries with a full system upgrade"
sudo pacman -Syu --noconfirm --needed "${packages[@]}"
log_step "Steam installed; launch Steam from GNOME or run steam as your normal user"
