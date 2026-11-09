#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=scripts/logging.sh
source "$SCRIPT_DIR/logging.sh"

if [[ "${SKIP_GITHUB_TRAY:-}" == "1" ]]; then
  log_step "Skipping GitHub Tray (SKIP_GITHUB_TRAY=1)"
  exit 0
fi

if [[ ${EUID:-$(id -u)} -eq 0 ]]; then
  echo "Please run this script as your regular user (not root/sudo)." >&2
  exit 1
fi

for tool in gnome-shell gnome-extensions; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "$tool is required; install GNOME before installing GitHub Tray." >&2
    exit 1
  fi
done

UUID="github-tray@debba.github.com"
VERSION=19
# Deliberately pinned to the upstream v19 release asset and its published digest.
DOWNLOAD_URL="https://github.com/debba/github-tray-gnome-extension/releases/download/v19/github-tray%40debba.github.com.zip"
SHA256="f032fb932cf41bf3c64326b30ae4d432d7e7dd1ec23fd331a5c4d722a05c6a65"
EXTENSION_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/gnome-shell/extensions/$UUID"
DONE_PATCH="$SCRIPT_DIR/../patches/github-tray-v19-done.patch"

if [[ -L "$EXTENSION_DIR" ]]; then
  echo "Refusing to replace a symlinked extension: $EXTENSION_DIR" >&2
  exit 1
fi

missing_packages=()
for package in curl jq unzip glib2 libsoup3 zenity patch; do
  if ! pacman -Q "$package" >/dev/null 2>&1; then
    missing_packages+=("$package")
  fi
done
if (( ${#missing_packages[@]} > 0 )); then
  log_step "Installing GitHub Tray dependencies"
  sudo pacman -S --noconfirm --needed "${missing_packages[@]}"
fi

shell_version=$(gnome-shell --version)
shell_version=${shell_version##* }
shell_version=${shell_version%%.*}

check_compatibility() {
  if ! jq -e --arg uuid "$UUID" --arg shell "$shell_version" \
      '.uuid == $uuid and (."shell-version" | index($shell) != null)' "$1" >/dev/null; then
    echo "GitHub Tray metadata does not declare support for GNOME $shell_version; leaving the installed extension unchanged." >&2
    exit 1
  fi
}

# Only patch compatible v19 sources; dry-run the entire patch before writing.
apply_done_patch() {
  local directory=$1 file
  local -a options=(--batch --force --fuzz=0 --no-backup-if-mismatch --reject-file=- -p1 -d "$directory")
  for file in githubApi.js notificationManager.js extension.js ui.js; do
    if [[ ! -f "$directory/$file" || -L "$directory/$file" ]]; then
      echo "Refusing to patch missing or symlinked GitHub Tray source: $directory/$file" >&2
      exit 1
    fi
  done
  if patch "${options[@]}" --reverse --dry-run < "$DONE_PATCH" >/dev/null 2>&1; then
    return
  fi
  if ! patch "${options[@]}" --forward --dry-run < "$DONE_PATCH" >/dev/null 2>&1; then
    echo "GitHub Tray sources do not match the v19 Done patch; leaving the extension unchanged." >&2
    exit 1
  fi
  if [[ "${2:-}" != "--dry-run" ]]; then
    patch "${options[@]}" --forward < "$DONE_PATCH"
    log_step "Added GitHub Tray Done action. Log out/in to load the updated extension."
  fi
}

if [[ -f "$EXTENSION_DIR/metadata.json" ]] &&
    jq -e --arg uuid "$UUID" --argjson version "$VERSION" \
      '.uuid == $uuid and (.version | type == "number") and .version >= $version' \
      "$EXTENSION_DIR/metadata.json" >/dev/null; then
  check_compatibility "$EXTENSION_DIR/metadata.json"
  if jq -e --argjson version "$VERSION" '.version == $version' "$EXTENSION_DIR/metadata.json" >/dev/null; then
    apply_done_patch "$EXTENSION_DIR"
  else
    log_step "Preserving newer GitHub Tray; the local Done patch only supports v$VERSION"
  fi
  if [[ ! -f "$EXTENSION_DIR/schemas/gschemas.compiled" ]]; then
    glib-compile-schemas --strict "$EXTENSION_DIR/schemas"
  fi
  log_step "GitHub Tray v$VERSION or newer is already installed; no download needed"
  "$SCRIPT_DIR/configure-github-tray.sh"
  exit 0
fi

TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT
BUNDLE="$TEMP_DIR/github-tray.zip"
log_step "Downloading GitHub Tray v$VERSION"
curl -fsSL "$DOWNLOAD_URL" -o "$BUNDLE"
if ! printf '%s  %s\n' "$SHA256" "$BUNDLE" | sha256sum --check --status; then
  echo "GitHub Tray checksum verification failed; leaving the installed extension unchanged." >&2
  exit 1
fi

unzip -q "$BUNDLE" -d "$TEMP_DIR/extension"
check_compatibility "$TEMP_DIR/extension/metadata.json"
if ! jq -e --argjson version "$VERSION" '.version == $version' \
    "$TEMP_DIR/extension/metadata.json" >/dev/null; then
  echo "Unexpected GitHub Tray version in the release bundle." >&2
  exit 1
fi
# Validate schemas before replacing an existing installation.
glib-compile-schemas --strict --dry-run "$TEMP_DIR/extension/schemas"
apply_done_patch "$TEMP_DIR/extension" --dry-run
gnome-extensions install --force "$BUNDLE"
apply_done_patch "$EXTENSION_DIR"
glib-compile-schemas --strict "$EXTENSION_DIR/schemas"
"$SCRIPT_DIR/configure-github-tray.sh"

log_step "GitHub Tray installed. Run scripts/enable-gnome-extensions.sh; a new extension may need logout/login first."
log_step "Configure your GitHub username and token manually in GitHub Tray preferences."
