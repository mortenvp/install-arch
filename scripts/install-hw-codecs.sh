#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=./logging.sh
source "$SCRIPT_DIR/logging.sh"

MODE="install"
if [[ "${1:-}" == "--check" ]]; then
  MODE="check"
elif [[ -n "${1:-}" ]]; then
  echo "Usage: $0 [--check]" >&2
  exit 1
fi

if ! command -v pacman >/dev/null 2>&1; then
  echo "pacman not found; this script must run on Arch Linux." >&2
  exit 2
fi

has_intel=false
has_amd=false
has_nvidia=false

detect_from_lspci() {
  [[ -x "$(command -v lspci 2>/dev/null || true)" ]] || return 0

  local gpu_lines
  gpu_lines="$(lspci -nn 2>/dev/null | grep -Ei 'VGA|3D|Display' || true)"
  [[ -n "$gpu_lines" ]] || return 0

  if grep -qi 'intel' <<<"$gpu_lines"; then
    has_intel=true
  fi
  if grep -Eqi 'amd|advanced micro devices|\[1002:|\[1022:' <<<"$gpu_lines"; then
    has_amd=true
  fi
  if grep -Eqi 'nvidia|\[10de:' <<<"$gpu_lines"; then
    has_nvidia=true
  fi
}

detect_from_sysfs() {
  local vendor_file
  for vendor_file in /sys/class/drm/card*/device/vendor; do
    [[ -f "$vendor_file" ]] || continue
    case "$(<"$vendor_file")" in
      0x8086) has_intel=true ;;
      0x1002|0x1022) has_amd=true ;;
      0x10de) has_nvidia=true ;;
    esac
  done
}

add_pkg() {
  local pkg="$1"
  for existing in "${recommended_packages[@]:-}"; do
    if [[ "$existing" == "$pkg" ]]; then
      return 0
    fi
  done
  recommended_packages+=("$pkg")
}

detect_from_lspci
detect_from_sysfs

recommended_packages=()

# CPU/software decode baseline
add_pkg "ffmpeg"
add_pkg "openh264"

if $has_intel || $has_amd || $has_nvidia; then
  add_pkg "libva"
  add_pkg "libvdpau"
  add_pkg "libva-utils"
  add_pkg "vdpauinfo"
fi

if $has_intel; then
  add_pkg "intel-media-driver"
fi

if $has_amd; then
  add_pkg "mesa"
  add_pkg "libvdpau-va-gl"
fi

if $has_nvidia; then
  add_pkg "libva-nvidia-driver"
fi

detected=()
$has_intel && detected+=("intel")
$has_amd && detected+=("amd")
$has_nvidia && detected+=("nvidia")

if (( ${#detected[@]} == 0 )); then
  log_step "No supported discrete/integrated GPU detected; installing CPU decode baseline"
else
  log_step "Detected GPU vendor(s): ${detected[*]}"
fi

available_packages=()
unavailable_packages=()
for pkg in "${recommended_packages[@]}"; do
  if pacman -Si "$pkg" >/dev/null 2>&1; then
    available_packages+=("$pkg")
  else
    unavailable_packages+=("$pkg")
  fi
done

if (( ${#unavailable_packages[@]} > 0 )); then
  log_step "Skipping unavailable package(s): ${unavailable_packages[*]}"
fi

if (( ${#available_packages[@]} == 0 )); then
  log_step "No available codec packages found for this system"
  exit 0
fi

log_step "Recommended codec packages: ${available_packages[*]}"

if [[ "$MODE" == "check" ]]; then
  log_step "Check mode enabled; not installing packages"
  exit 0
fi

missing_packages=()
for pkg in "${available_packages[@]}"; do
  if ! pacman -Q "$pkg" >/dev/null 2>&1; then
    missing_packages+=("$pkg")
  fi
done

if (( ${#missing_packages[@]} == 0 )); then
  log_step "All recommended codec packages already installed; skipping"
  exit 0
fi

log_step "Installing ${#missing_packages[@]} codec package(s)"
sudo pacman -S --noconfirm --needed "${missing_packages[@]}"
