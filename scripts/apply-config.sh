#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
ROOT_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
# shellcheck source=./logging.sh
source "$SCRIPT_DIR/logging.sh"

log_step "Applying config files"
VSCODE_SETTINGS_SRC="$ROOT_DIR/config/Code/User/settings.json"
VSCODE_SETTINGS_TARGET="$HOME/.config/Code/User/settings.json"
VSCODE_SETTINGS_BACKUP=""
GIT_CONFIG_TARGET="$HOME/.config/git/config"
FISH_CONFIG_SRC="$ROOT_DIR/config/fish/config.fish"
FISH_CONFIG_TARGET="$HOME/.config/fish/config.fish"
EXISTING_GIT_NAME=""
EXISTING_GIT_EMAIL=""

prompt_yes_no() {
  local prompt="$1"
  local answer=""

  read -r -p "$prompt [y/N]: " answer || true
  case "$answer" in
    [Yy]|[Yy][Ee][Ss])
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

is_valid_json_object() {
  local file_path="$1"
  jq -e 'type == "object"' "$file_path" >/dev/null 2>&1
}

apply_vscode_settings() {
  if [[ ! -f "$VSCODE_SETTINGS_SRC" ]]; then
    return
  fi

  mkdir -p "$(dirname "$VSCODE_SETTINGS_TARGET")"

  if [[ -z "$VSCODE_SETTINGS_BACKUP" ]]; then
    install -m 644 "$VSCODE_SETTINGS_SRC" "$VSCODE_SETTINGS_TARGET"
    log_step "Applied VS Code settings defaults to $VSCODE_SETTINGS_TARGET"
    return
  fi

  if ! is_valid_json_object "$VSCODE_SETTINGS_SRC"; then
    echo "Invalid VS Code settings JSON at $VSCODE_SETTINGS_SRC" >&2
    exit 1
  fi

  if ! is_valid_json_object "$VSCODE_SETTINGS_BACKUP"; then
    if [[ -t 0 && -t 1 ]]; then
      log_step "Existing VS Code settings are not valid JSON"
      if prompt_yes_no "Overwrite VS Code settings with repo defaults?"; then
        install -m 644 "$VSCODE_SETTINGS_SRC" "$VSCODE_SETTINGS_TARGET"
        log_step "Overwrote VS Code settings at $VSCODE_SETTINGS_TARGET"
      else
        install -m 644 "$VSCODE_SETTINGS_BACKUP" "$VSCODE_SETTINGS_TARGET"
        log_step "Preserved existing VS Code settings at $VSCODE_SETTINGS_TARGET"
      fi
    else
      install -m 644 "$VSCODE_SETTINGS_SRC" "$VSCODE_SETTINGS_TARGET"
      log_step "Existing VS Code settings are not valid JSON; overwrote with repo defaults (non-interactive mode)"
    fi

    return
  fi

  local compare_json=""
  compare_json=$(jq -n \
    --slurpfile src "$VSCODE_SETTINGS_SRC" \
    --slurpfile local "$VSCODE_SETTINGS_BACKUP" \
    '{
      missing: [($src[0] | keys[] as $k | select(($local[0] | has($k)) | not) | $k)],
      conflicts: [($src[0] | keys[] as $k | select(($local[0] | has($k)) and ($local[0][$k] != $src[0][$k])) | $k)]
    }')

  local missing_count="0"
  local conflict_count="0"
  missing_count=$(jq '.missing | length' <<<"$compare_json")
  conflict_count=$(jq '.conflicts | length' <<<"$compare_json")

  local overwrite_conflicts="false"
  if (( conflict_count > 0 )); then
    local conflict_keys=""
    conflict_keys=$(jq -r '.conflicts | join(", ")' <<<"$compare_json")

    if [[ -t 0 && -t 1 ]]; then
      log_step "VS Code settings conflicts detected: $conflict_keys"
      if prompt_yes_no "Overwrite conflicting VS Code keys with repo defaults?"; then
        overwrite_conflicts="true"
      fi
    else
      overwrite_conflicts="true"
      log_step "VS Code settings conflicts detected; overwriting conflicting keys (non-interactive mode)"
    fi
  fi

  local merged_tmp=""
  merged_tmp=$(mktemp)

  if [[ "$overwrite_conflicts" == "true" ]]; then
    jq -n \
      --slurpfile src "$VSCODE_SETTINGS_SRC" \
      --slurpfile local "$VSCODE_SETTINGS_BACKUP" \
      '$local[0] + $src[0]' >"$merged_tmp"
    install -m 644 "$merged_tmp" "$VSCODE_SETTINGS_TARGET"
    log_step "Applied VS Code settings and overwrote $conflict_count conflicting key(s); kept local-only keys"
  else
    jq -n \
      --slurpfile src "$VSCODE_SETTINGS_SRC" \
      --slurpfile local "$VSCODE_SETTINGS_BACKUP" \
      '$src[0] + $local[0]' >"$merged_tmp"
    install -m 644 "$merged_tmp" "$VSCODE_SETTINGS_TARGET"

    if (( conflict_count > 0 )); then
      log_step "Kept local values for $conflict_count conflicting VS Code key(s); added $missing_count missing key(s)"
    elif (( missing_count > 0 )); then
      log_step "Applied VS Code settings by adding $missing_count missing key(s)"
    else
      log_step "VS Code settings already up to date"
    fi
  fi

  rm -f "$merged_tmp"
}

if [[ -f "$VSCODE_SETTINGS_SRC" ]] && ! command -v jq >/dev/null 2>&1; then
  echo "jq is required to merge VS Code settings. Install jq and retry." >&2
  exit 1
fi

if command -v git >/dev/null 2>&1; then
  EXISTING_GIT_NAME=$(git config --global --get user.name || true)
  EXISTING_GIT_EMAIL=$(git config --global --get user.email || true)
fi

if [[ -f "$VSCODE_SETTINGS_TARGET" ]]; then
  VSCODE_SETTINGS_BACKUP=$(mktemp)
  cp "$VSCODE_SETTINGS_TARGET" "$VSCODE_SETTINGS_BACKUP"
fi

# Copy ~/.config files
if [[ -d "$ROOT_DIR/config" ]]; then
  mkdir -p "$HOME/.config"
  cp -R "$ROOT_DIR/config/"* "$HOME/.config/" 2>/dev/null || true
fi

apply_vscode_settings

if [[ -n "$VSCODE_SETTINGS_BACKUP" ]]; then
  rm -f "$VSCODE_SETTINGS_BACKUP"
fi

if [[ -n "$EXISTING_GIT_NAME" || -n "$EXISTING_GIT_EMAIL" ]]; then
  mkdir -p "$(dirname "$GIT_CONFIG_TARGET")"
  if [[ -n "$EXISTING_GIT_NAME" ]]; then
    git config --file "$GIT_CONFIG_TARGET" user.name "$EXISTING_GIT_NAME"
  fi
  if [[ -n "$EXISTING_GIT_EMAIL" ]]; then
    git config --file "$GIT_CONFIG_TARGET" user.email "$EXISTING_GIT_EMAIL"
  fi
  log_step "Preserved existing git user identity in $GIT_CONFIG_TARGET"
fi

log_step "Ensuring fish config directory exists"
# Ensure fish config directory exists
mkdir -p "$HOME/.config/fish"

if [[ -f "$FISH_CONFIG_SRC" ]]; then
  install -m 644 "$FISH_CONFIG_SRC" "$FISH_CONFIG_TARGET"
  log_step "Applied fish config to $FISH_CONFIG_TARGET"
fi
