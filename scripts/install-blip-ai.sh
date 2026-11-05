#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=scripts/logging.sh
source "$SCRIPT_DIR/logging.sh"

if [[ "${SKIP_BLIP_AI:-}" == "1" ]]; then
  log_step "Skipping Blip AI (SKIP_BLIP_AI=1)"
  exit 0
fi

if [[ ${EUID:-$(id -u)} -eq 0 ]]; then
  echo "Please run this script as your regular user (not root/sudo)." >&2
  exit 1
fi

if [[ "$(uname -m)" != "x86_64" ]]; then
  log_step "Blip AI only provides an x86_64 Linux AppImage; skipping"
  exit 0
fi

APPIMAGE="$HOME/.local/bin/BlipAI.AppImage"
RELEASES_URL="https://api.github.com/repos/abnsl0014/blipai-releases/releases/latest"

missing_packages=()
for package in curl jq fuse2 wtype wl-clipboard ydotool; do
  if ! pacman -Q "$package" >/dev/null 2>&1; then
    missing_packages+=("$package")
  fi
done
if (( ${#missing_packages[@]} > 0 )); then
  log_step "Installing Blip AI dependencies"
  sudo pacman -S --noconfirm --needed "${missing_packages[@]}"
fi

TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

if [[ -x "$APPIMAGE" ]]; then
  log_step "Blip AI AppImage already installed; leaving it unchanged"
else
  log_step "Downloading the latest official Blip AI AppImage"
  curl -fsSL "$RELEASES_URL" -o "$TEMP_DIR/release.json"
  asset=$(jq -er '
    [.assets[] | select(.name | test("^Blip-AI-[0-9]+(\\.[0-9]+)*\\.AppImage$"))]
    | if length == 1 then .[0] else error("Expected one Blip AI Linux AppImage") end
    | [.browser_download_url, .digest] | @tsv
  ' "$TEMP_DIR/release.json")
  IFS=$'\t' read -r download_url digest <<< "$asset"
  if [[ "$download_url" != https://github.com/abnsl0014/blipai-releases/releases/download/*/Blip-AI-*.AppImage ||
        ! "$digest" =~ ^sha256:[a-fA-F0-9]{64}$ ]]; then
    echo "The Blip AI release has no valid AppImage URL or SHA-256 digest." >&2
    exit 1
  fi

  # Download and verify completely before installing; never launch during setup.
  curl -fsSL "$download_url" -o "$TEMP_DIR/BlipAI.AppImage"
  if ! printf '%s  %s\n' "${digest#sha256:}" "$TEMP_DIR/BlipAI.AppImage" |
      sha256sum --check --status; then
    echo "Blip AI AppImage checksum verification failed." >&2
    exit 1
  fi
  install -Dm755 "$TEMP_DIR/BlipAI.AppImage" "$APPIMAGE"
fi

"$SCRIPT_DIR/configure-blip-ai.sh"

log_step "Blip AI installed. Open Blip AI from GNOME or run $APPIMAGE."
log_step "Wayland needs input-group access and the ydotool user service; see README.md before granting these permissions."
