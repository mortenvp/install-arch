#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=./logging.sh
source "$SCRIPT_DIR/logging.sh"

if ! command -v gnome-extensions >/dev/null 2>&1; then
  echo "gnome-extensions not found. Install GNOME and gnome-shell extensions tooling." >&2
  exit 1
fi

if command -v gsettings >/dev/null 2>&1; then
  disable_user_extensions="$(gsettings get org.gnome.shell disable-user-extensions 2>/dev/null || true)"
  if [[ "$disable_user_extensions" == "true" ]]; then
    log_step "GNOME user extensions are globally disabled; enabling them"
    if gsettings set org.gnome.shell disable-user-extensions false; then
      log_step "Enabled GNOME user extensions globally"
    else
      log_step "Could not update org.gnome.shell disable-user-extensions; continuing with per-extension enables"
    fi
  fi
fi

POP_SHELL_UUID="pop-shell@system76.com"
ARCH_UPDATE_UUID="arch-update@RaphaelRochet"
GSCONNECT_UUID="gsconnect@andyholmes.github.io"

mapfile -t installed_extensions < <(gnome-extensions list)

enabled_any=0

if printf '%s\n' "${installed_extensions[@]}" | grep -q "^${POP_SHELL_UUID}$"; then
  log_step "Enabling Pop Shell (${POP_SHELL_UUID})"
  gnome-extensions enable "$POP_SHELL_UUID"
  enabled_any=1
else
  log_step "Pop Shell extension not found; skipping"
fi

if printf '%s\n' "${installed_extensions[@]}" | grep -q "^${ARCH_UPDATE_UUID}$"; then
  log_step "Enabling Arch Update Indicator (${ARCH_UPDATE_UUID})"
  gnome-extensions enable "$ARCH_UPDATE_UUID"
  enabled_any=1
else
  if [[ -d "/usr/share/gnome-shell/extensions/${ARCH_UPDATE_UUID}" || -d "$HOME/.local/share/gnome-shell/extensions/${ARCH_UPDATE_UUID}" ]]; then
    log_step "Arch Update Indicator files found; attempting to enable (${ARCH_UPDATE_UUID})"
    if gnome-extensions enable "$ARCH_UPDATE_UUID"; then
      enabled_any=1
    else
      log_step "Arch Update Indicator is installed but not visible to the current GNOME Shell session; log out/in and run this script again"
    fi
  else
    log_step "Arch Update Indicator extension not found; skipping"
  fi
fi

if printf '%s\n' "${installed_extensions[@]}" | grep -q "^${GSCONNECT_UUID}$"; then
  log_step "Enabling GSConnect (${GSCONNECT_UUID})"
  gnome-extensions enable "$GSCONNECT_UUID"
  enabled_any=1
else
  if [[ -d "/usr/share/gnome-shell/extensions/${GSCONNECT_UUID}" || -d "$HOME/.local/share/gnome-shell/extensions/${GSCONNECT_UUID}" ]]; then
    log_step "GSConnect files found; attempting to enable (${GSCONNECT_UUID})"
    if gnome-extensions enable "$GSCONNECT_UUID"; then
      enabled_any=1
    else
      log_step "GSConnect is installed but not visible to the current GNOME Shell session; log out/in and run this script again"
    fi
  else
    log_step "GSConnect extension not found; skipping"
  fi
fi

appindicator_uuid="$(printf '%s\n' "${installed_extensions[@]}" | grep '^appindicatorsupport@' | head -n 1 || true)"
if [[ -n "$appindicator_uuid" ]]; then
  log_step "Enabling AppIndicator (${appindicator_uuid})"
  gnome-extensions enable "$appindicator_uuid"
  enabled_any=1
else
  if [[ -d /usr/share/gnome-shell/extensions/appindicatorsupport@rgcjonas.gmail.com ]]; then
    log_step "AppIndicator files found; attempting to enable (${appindicator_uuid:-appindicatorsupport@rgcjonas.gmail.com})"
    if gnome-extensions enable "${appindicator_uuid:-appindicatorsupport@rgcjonas.gmail.com}"; then
      enabled_any=1
    else
      log_step "AppIndicator is installed but not visible to the current GNOME Shell session; log out/in and run this script again"
    fi
  else
    log_step "AppIndicator extension not found; skipping"
  fi
fi

if [[ "$enabled_any" -eq 0 ]]; then
  log_step "No target GNOME extensions found to enable"
fi
