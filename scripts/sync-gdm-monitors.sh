#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=./logging.sh
if [[ -r "$SCRIPT_DIR/logging.sh" ]]; then
  source "$SCRIPT_DIR/logging.sh"
else
  log_step() {
    printf '\n==> %s\n' "$*"
  }
fi

SOURCE_MONITORS_XML="${HOME:-/root}/.config/monitors.xml"
TARGET_MONITORS_XML="/etc/xdg/monitors.xml"
GDM_MONITORS_XML="/var/lib/gdm/.config/monitors.xml"
UPDATE_SOURCE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --update-source)
      UPDATE_SOURCE=1
      shift
      ;;
    --no-update-source)
      UPDATE_SOURCE=0
      shift
      ;;
    -h|--help)
      cat <<EOF
Usage: $0 [--update-source] [SOURCE_MONITORS_XML]

Sync a GNOME monitors.xml layout to GDM. When possible, connector names are
rewritten from the currently connected monitor EDIDs before syncing.
EOF
      exit 0
      ;;
    *)
      SOURCE_MONITORS_XML=$1
      shift
      ;;
  esac
done

run_as_root() {
  if [[ ${EUID:-$(id -u)} -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

install_for_current_user() {
  local source=$1
  local target=$2
  local mode owner_group

  mode=$(stat -c '%a' "$target" 2>/dev/null || printf '644')
  owner_group=$(stat -c '%u:%g' "$target" 2>/dev/null || printf '')

  if [[ ${EUID:-$(id -u)} -eq 0 ]]; then
    install -m "$mode" "$source" "$target"
    if [[ -n "$owner_group" ]]; then
      chown "$owner_group" "$target"
    fi
  else
    install -m "$mode" "$source" "$target"
  fi
}

if [[ ! -f "$SOURCE_MONITORS_XML" ]]; then
  log_step "No monitors.xml at $SOURCE_MONITORS_XML; skipping GDM monitor sync"
  exit 0
fi

ACTIVE_MONITORS_XML="$SOURCE_MONITORS_XML"
RENDERED_MONITORS_XML=
RENDERER=

for candidate in \
  "$SCRIPT_DIR/render-gdm-monitors.py" \
  /usr/local/lib/install-arch/render-gdm-monitors.py; do
  if [[ -x "$candidate" || -f "$candidate" ]]; then
    RENDERER=$candidate
    break
  fi
done

PYTHON_BIN=
if [[ -n "$RENDERER" ]] && PYTHON_BIN=$(command -v python3 2>/dev/null); then
  RENDERED_MONITORS_XML=$(mktemp)
  trap '[[ -n "${RENDERED_MONITORS_XML:-}" ]] && rm -f "$RENDERED_MONITORS_XML"' EXIT

  if "$PYTHON_BIN" "$RENDERER" "$SOURCE_MONITORS_XML" >"$RENDERED_MONITORS_XML"; then
    ACTIVE_MONITORS_XML="$RENDERED_MONITORS_XML"
    log_step "Rendered monitor layout with current DRM connector names"
  else
    log_step "Could not render monitor layout; falling back to direct copy"
  fi
else
  log_step "Monitor renderer or python3 not available; falling back to direct copy"
fi

if [[ "$UPDATE_SOURCE" == "1" && "$ACTIVE_MONITORS_XML" != "$SOURCE_MONITORS_XML" ]]; then
  if cmp -s "$ACTIVE_MONITORS_XML" "$SOURCE_MONITORS_XML"; then
    log_step "$SOURCE_MONITORS_XML already has current connector names"
  else
    log_step "Updating $SOURCE_MONITORS_XML with current connector names"
    install_for_current_user "$ACTIVE_MONITORS_XML" "$SOURCE_MONITORS_XML"
  fi
fi

log_step "Syncing monitor layout to $TARGET_MONITORS_XML"
run_as_root install -d -m 755 /etc/xdg
run_as_root install -m 644 "$ACTIVE_MONITORS_XML" "$TARGET_MONITORS_XML"

log_step "Syncing monitor layout to $GDM_MONITORS_XML"
run_as_root install -d -m 755 /var/lib/gdm/.config
run_as_root install -m 644 "$ACTIVE_MONITORS_XML" "$GDM_MONITORS_XML"
if getent passwd gdm >/dev/null 2>&1; then
  run_as_root chown gdm:gdm "$GDM_MONITORS_XML"
fi
