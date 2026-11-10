#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=scripts/logging.sh
source "$SCRIPT_DIR/logging.sh"

if [[ "${SKIP_HERDR:-}" == "1" || "${SKIP_HERDR_WORKTREES:-}" == "1" ]]; then
  log_step "Skipping Herdr worktree layout (SKIP_HERDR or SKIP_HERDR_WORKTREES=1)"
  exit 0
fi

if [[ ${EUID:-$(id -u)} -eq 0 ]]; then
  echo "Please run this script as your regular user (not root/sudo)." >&2
  exit 1
fi

if (( $# > 1 )) || [[ "${1:-}" != "" && "${1:-}" != --uninstall ]]; then
  echo "Usage: $0 [--uninstall]" >&2
  exit 1
fi

export PATH="$HOME/.local/bin:$PATH"
export HERDR_APP_HOME="${HERDR_APP_HOME:-${XDG_CONFIG_HOME:-$HOME/.config}/herdr-app}"
if ! command -v herdr-app >/dev/null 2>&1; then
  echo "herdr-app is required; run scripts/install-herdr.sh first." >&2
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  sudo pacman -S --noconfirm --needed python
fi

log_step "Configuring Herdr worktrees to match WT (sibling .worktrees directory)"
python3 "$SCRIPT_DIR/herdr-worktrees.py" "$@"
