#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=scripts/logging.sh
source "$SCRIPT_DIR/logging.sh"

PACKAGE_LIST="${1:-$(dirname "$0")/../packages/base.packages}"

if [[ ! -f "$PACKAGE_LIST" ]]; then
  echo "Package list not found: $PACKAGE_LIST" >&2
  exit 1
fi

mapfile -t packages < <(grep -v '^#' "$PACKAGE_LIST" | grep -v '^$')

if (( ${#packages[@]} == 0 )); then
  echo "No packages found in $PACKAGE_LIST" >&2
  exit 1
fi

missing_packages=()
for pkg in "${packages[@]}"; do
  if ! pacman -Q "$pkg" >/dev/null 2>&1; then
    missing_packages+=("$pkg")
  fi
done

if (( ${#missing_packages[@]} == 0 )); then
  log_step "All ${#packages[@]} packages already installed; skipping"
  exit 0
fi

fail_on_unowned_node_conflicts() {
  local -a candidates=()

  if printf '%s\n' "${missing_packages[@]}" | grep -qx 'pnpm'; then
    candidates+=(
      /usr/bin/pn
      /usr/bin/pnx
      /usr/lib/node_modules/pnpm
    )
  fi

  if printf '%s\n' "${missing_packages[@]}" | grep -qx 'typescript'; then
    candidates+=(
      /usr/lib/node_modules/typescript
    )
  fi

  if (( ${#candidates[@]} == 0 )); then
    return 0
  fi

  local -a conflicts=()
  for path in "${candidates[@]}"; do
    [[ -e "$path" ]] || continue

    if ! pacman -Qo "$path" >/dev/null 2>&1; then
      conflicts+=("$path")
    fi
  done

  if (( ${#conflicts[@]} > 0 )); then
    echo "Refusing to continue due to npm-global files in /usr conflicting with pacman packages:" >&2
    printf '  - %s\n' "${conflicts[@]}" >&2
    echo "Fix: remove these paths, then rerun install." >&2
    echo "Policy: install system tools via pacman/AUR, and use user-local npm globals (~/.local) only." >&2
    exit 1
  fi
}

fail_on_unowned_node_conflicts

log_step "Installing ${#missing_packages[@]} missing packages from $PACKAGE_LIST"
sudo pacman -S --noconfirm --needed "${missing_packages[@]}"
