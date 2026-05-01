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
  log_step "pacman not found; skipping NVIDIA display setup"
  exit 0
fi

has_nvidia=false

if command -v lspci >/dev/null 2>&1; then
  if lspci -nn 2>/dev/null | grep -Eqi 'VGA|3D|Display' && \
     lspci -nn 2>/dev/null | grep -Eqi 'nvidia|\[10de:'; then
    has_nvidia=true
  fi
fi

for vendor_file in /sys/class/drm/card*/device/vendor; do
  [[ -f "$vendor_file" ]] || continue
  if [[ "$(<"$vendor_file")" == "0x10de" ]]; then
    has_nvidia=true
  fi
done

if ! $has_nvidia; then
  log_step "No NVIDIA GPU detected; skipping NVIDIA display setup"
  exit 0
fi

installed_packages="$(pacman -Qq)"
package_installed() {
  grep -Fxq "$1" <<<"$installed_packages"
}

packages=(nvidia-utils)
changed=false

has_nvidia_driver=false
has_dkms_nvidia_driver=false
for driver_pkg in nvidia-open-dkms nvidia-dkms nvidia-open nvidia; do
  if package_installed "$driver_pkg"; then
    has_nvidia_driver=true
    case "$driver_pkg" in
      nvidia-open-dkms|nvidia-dkms) has_dkms_nvidia_driver=true ;;
    esac
  fi
done

if ! $has_nvidia_driver; then
  packages+=(linux-headers nvidia-open-dkms)
elif $has_dkms_nvidia_driver; then
  packages+=(linux-headers)
fi

missing_packages=()
for pkg in "${packages[@]}"; do
  if ! package_installed "$pkg"; then
    missing_packages+=("$pkg")
  fi
done

if (( ${#missing_packages[@]} > 0 )); then
  log_step "Missing NVIDIA display package(s): ${missing_packages[*]}"
  if [[ "$MODE" == "check" ]]; then
    log_step "Check mode enabled; not installing packages"
  else
    sudo pacman -S --noconfirm --needed "${missing_packages[@]}"
    changed=true
  fi
else
  log_step "NVIDIA display packages already installed"
fi

if ! command -v mkinitcpio >/dev/null 2>&1; then
  log_step "mkinitcpio not found; skipping NVIDIA early KMS setup"
  exit 0
fi

drop_in_dir="/etc/mkinitcpio.conf.d"
drop_in_file="$drop_in_dir/90-nvidia-early-kms.conf"

read -r -d '' drop_in_content <<'EOF' || true
# Managed by install-arch.
# Load NVIDIA DRM before GDM/Wayland starts so monitor probing completes
# before the display manager reads the available GPUs and connectors.
MODULES+=(nvidia nvidia_modeset nvidia_uvm nvidia_drm)
EOF

if [[ -r "$drop_in_file" ]] && [[ "$(<"$drop_in_file")" == "$drop_in_content" ]]; then
  log_step "$drop_in_file already configured"
else
  log_step "Configuring NVIDIA early KMS in $drop_in_file"
  if [[ "$MODE" == "check" ]]; then
    log_step "Check mode enabled; not writing mkinitcpio drop-in"
  else
    sudo install -d -m 755 "$drop_in_dir"
    printf '%s\n' "$drop_in_content" | sudo tee "$drop_in_file" >/dev/null
    changed=true
  fi
fi

if [[ "$MODE" == "check" ]]; then
  log_step "Check mode enabled; not rebuilding initramfs"
  exit 0
fi

if ! $changed; then
  log_step "NVIDIA early KMS already configured; skipping initramfs rebuild"
  exit 0
fi

log_step "Regenerating initramfs with NVIDIA early KMS modules"
sudo mkinitcpio -P
