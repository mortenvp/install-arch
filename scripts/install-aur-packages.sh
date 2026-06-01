#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=./logging.sh
source "$SCRIPT_DIR/logging.sh"

PACKAGE_LIST="${1:-$(dirname "$0")/../packages/aur.packages}"

if [[ ! -f "$PACKAGE_LIST" ]]; then
  echo "Package list not found: $PACKAGE_LIST" >&2
  exit 1
fi

ensure_yay() {
  if command -v yay >/dev/null 2>&1; then
    return 0
  fi

  log_step "Installing yay-bin (AUR helper)"
  sudo pacman -S --noconfirm --needed base-devel git

  local tmp_dir
  tmp_dir="$(mktemp -d)"
  trap 'rm -rf "$tmp_dir"' RETURN

  git clone https://aur.archlinux.org/yay-bin.git "$tmp_dir/yay-bin"
  (
    cd "$tmp_dir/yay-bin"
    makepkg -si --noconfirm
  )

  if ! command -v yay >/dev/null 2>&1; then
    echo "Failed to install yay from yay-bin." >&2
    exit 1
  fi
}

mapfile -t packages < <(grep -v '^#' "$PACKAGE_LIST" | grep -v '^$')

if (( ${#packages[@]} == 0 )); then
  echo "No packages found in $PACKAGE_LIST" >&2
  exit 1
fi

# gnome-shell-extension-pop-shell-git's build checks for `tsc` on PATH but does not
# reliably pull TypeScript as an Arch package dependency.
if printf '%s\n' "${packages[@]}" | grep -qx 'gnome-shell-extension-pop-shell-git'; then
  if ! command -v tsc >/dev/null 2>&1; then
    log_step "tsc not found; installing TypeScript for pop-shell build"
    sudo pacman -S --noconfirm typescript
  fi
fi

missing_packages=()
installed_devel_packages=()
for pkg in "${packages[@]}"; do
  if ! pacman -Q "$pkg" >/dev/null 2>&1; then
    missing_packages+=("$pkg")
  elif [[ "$pkg" =~ -(git|hg|svn|bzr|darcs|cvs)$ ]]; then
    installed_devel_packages+=("$pkg")
  fi
done

if (( ${#missing_packages[@]} == 0 && ${#installed_devel_packages[@]} == 0 )); then
  log_step "All ${#packages[@]} AUR packages already installed; skipping"
  exit 0
fi

"$SCRIPT_DIR/cleanup-npm-global-conflicts.sh"

ensure_yay

if (( ${#missing_packages[@]} > 0 )); then
  log_step "Installing ${#missing_packages[@]} missing AUR packages from $PACKAGE_LIST"
  yay -S --noconfirm --needed "${missing_packages[@]}"
fi

if (( ${#installed_devel_packages[@]} > 0 )); then
  log_step "Refreshing ${#installed_devel_packages[@]} devel package(s) from $PACKAGE_LIST"
  yay -S --noconfirm --devel "${installed_devel_packages[@]}"
fi
