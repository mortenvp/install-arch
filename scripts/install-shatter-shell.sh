#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=scripts/logging.sh
source "$SCRIPT_DIR/logging.sh"

if [[ "${SKIP_SHATTER_SHELL:-}" == "1" ]]; then
  log_step "Skipping Shatter Shell (SKIP_SHATTER_SHELL=1)"
  exit 0
fi

if [[ ${EUID:-$(id -u)} -eq 0 ]]; then
  echo "Please run this script as your regular user (not root/sudo)." >&2
  exit 1
fi

REPOSITORY="https://github.com/adil192/shatter-shell.git"
BRANCH="master_resolute"
SOURCE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/install-arch/shatter-shell"
EXTENSIONS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/gnome-shell/extensions"

missing_packages=()
for dependency in git:git make:make node:nodejs npm:npm jq:jq glib-compile-schemas:glib2; do
  if ! command -v "${dependency%%:*}" >/dev/null 2>&1; then
    missing_packages+=("${dependency#*:}")
  fi
done
if (( ${#missing_packages[@]} > 0 )); then
  log_step "Installing Shatter Shell build dependencies"
  sudo pacman -S --noconfirm --needed "${missing_packages[@]}"
fi

if [[ -e "$SOURCE_DIR" ]]; then
  if [[ "$(git -C "$SOURCE_DIR" remote get-url origin)" != "$REPOSITORY" ||
        "$(git -C "$SOURCE_DIR" branch --show-current)" != "$BRANCH" ||
        -n "$(git -C "$SOURCE_DIR" status --porcelain)" ]]; then
    echo "Refusing to overwrite a modified or unexpected checkout: $SOURCE_DIR" >&2
    exit 1
  fi
  log_step "Updating Shatter Shell ($BRANCH)"
  git -C "$SOURCE_DIR" pull --ff-only
else
  log_step "Cloning Shatter Shell ($BRANCH)"
  mkdir -p "$(dirname "$SOURCE_DIR")"
  git clone --single-branch --branch "$BRANCH" "$REPOSITORY" "$SOURCE_DIR"
fi

if command -v gnome-shell >/dev/null 2>&1; then
  shell_version=$(gnome-shell --version)
  shell_version=${shell_version##* }
  shell_version=${shell_version%%.*}
  if ! jq -e --arg version "$shell_version" '."shell-version" | index($version) != null' \
      "$SOURCE_DIR/metadata.json" >/dev/null; then
    echo "Shatter Shell does not declare support for GNOME $shell_version; leaving the installed extension unchanged." >&2
    exit 1
  fi
fi

log_step "Building and installing Shatter Shell into $EXTENSIONS_DIR"
(
  cd "$SOURCE_DIR"
  # Use the project's locked TypeScript/Sass versions, not global npm tools.
  export PATH="$SOURCE_DIR/node_modules/.bin:$PATH"
  make clean
  make compile
  # Unlike gnome-extensions install, make install does not compile schemas.
  glib-compile-schemas _build/schemas
  # Avoid upstream local-install: enabling/configuration belongs in a separate step.
  make install DESTDIR= INSTALLBASE="$EXTENSIONS_DIR"
)

log_step "Shatter Shell installed. Log out/in to load a new or updated extension, then run scripts/enable-gnome-extensions.sh."
