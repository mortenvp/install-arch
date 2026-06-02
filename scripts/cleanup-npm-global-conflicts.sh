#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=./logging.sh
source "$SCRIPT_DIR/logging.sh"

# Top-level paths that often conflict when previously installed via `npm -g` with sudo.
EXACT_PATHS=(
  /usr/bin/pn
  /usr/bin/pnx
)

# Whole global npm package trees that are safe to remove only when the top-level
# tree is not owned by pacman.
NODE_MODULE_TREES=(
  /usr/lib/node_modules/pnpm
  /usr/lib/node_modules/typescript
)

# Known unowned files created by `sudo npm update -g npm` that conflict with the
# Arch npm package upgrade. Keep this targeted: recursively pruning pacman-owned
# npm trees can leave npm broken before pacman reinstalls it.
NPM_CONFLICT_PATHS=(
  /usr/lib/node_modules/npm/docs/content/commands/npm-approve-scripts.md
  /usr/lib/node_modules/npm/docs/content/commands/npm-deny-scripts.md
  /usr/lib/node_modules/npm/docs/content/commands/npm-stage.md
  /usr/lib/node_modules/npm/docs/output/commands/npm-approve-scripts.html
  /usr/lib/node_modules/npm/docs/output/commands/npm-deny-scripts.html
  /usr/lib/node_modules/npm/docs/output/commands/npm-stage.html
  /usr/lib/node_modules/npm/lib/commands/approve-scripts.js
  /usr/lib/node_modules/npm/lib/commands/deny-scripts.js
  /usr/lib/node_modules/npm/lib/commands/stage/approve.js
  /usr/lib/node_modules/npm/lib/commands/stage/download.js
  /usr/lib/node_modules/npm/lib/commands/stage/index.js
  /usr/lib/node_modules/npm/lib/commands/stage/list.js
  /usr/lib/node_modules/npm/lib/commands/stage/publish.js
  /usr/lib/node_modules/npm/lib/commands/stage/reject.js
  /usr/lib/node_modules/npm/lib/commands/stage/view.js
  /usr/lib/node_modules/npm/lib/utils/allow-scripts-cmd.js
  /usr/lib/node_modules/npm/lib/utils/allow-scripts-writer.js
  /usr/lib/node_modules/npm/lib/utils/check-allow-scripts.js
  /usr/lib/node_modules/npm/lib/utils/key-values.js
  /usr/lib/node_modules/npm/lib/utils/resolve-allow-scripts.js
  /usr/lib/node_modules/npm/lib/utils/strict-allow-scripts-preflight.js
  /usr/lib/node_modules/npm/lib/utils/validate-uuid.js
  /usr/lib/node_modules/npm/lib/utils/warn-workspace-allow-scripts.js
  /usr/lib/node_modules/npm/node_modules/@npmcli/arborist/lib/install-scripts.js
  /usr/lib/node_modules/npm/node_modules/@npmcli/arborist/lib/script-allowed.js
  /usr/lib/node_modules/npm/node_modules/@npmcli/config/lib/parse-allow-scripts-list.js
  /usr/lib/node_modules/npm/node_modules/lru-cache/dist/commonjs/browser/diagnostics-channel.js
  /usr/lib/node_modules/npm/node_modules/lru-cache/dist/commonjs/browser/index.js
  /usr/lib/node_modules/npm/node_modules/lru-cache/dist/commonjs/browser/index.min.js
  /usr/lib/node_modules/npm/node_modules/lru-cache/dist/commonjs/browser/perf.js
  /usr/lib/node_modules/npm/node_modules/lru-cache/dist/commonjs/node/diagnostics-channel.js
  /usr/lib/node_modules/npm/node_modules/lru-cache/dist/commonjs/node/index.js
  /usr/lib/node_modules/npm/node_modules/lru-cache/dist/commonjs/node/index.min.js
  /usr/lib/node_modules/npm/node_modules/lru-cache/dist/commonjs/node/perf.js
  /usr/lib/node_modules/npm/node_modules/lru-cache/dist/commonjs/perf.js
  /usr/lib/node_modules/npm/node_modules/lru-cache/dist/esm/browser/perf.js
  /usr/lib/node_modules/npm/node_modules/lru-cache/dist/esm/node/perf.js
  /usr/lib/node_modules/npm/node_modules/lru-cache/dist/esm/perf.js
)

removed=0
npm_touched=0

mark_removal_started() {
  if (( removed == 0 )); then
    log_step "Removing unowned npm-global paths under /usr that conflict with pacman"
  fi
  removed=1
}

remove_unowned_path() {
  local path="$1"
  [[ -e "$path" || -L "$path" ]] || return 0

  if pacman -Qo "$path" >/dev/null 2>&1; then
    return 0
  fi

  mark_removal_started
  sudo rm -rf -- "$path"
  echo "removed: $path"
}

for path in "${EXACT_PATHS[@]}"; do
  remove_unowned_path "$path"
done

for tree in "${NODE_MODULE_TREES[@]}"; do
  [[ -d "$tree" ]] || continue

  if ! pacman -Qo "$tree" >/dev/null 2>&1; then
    remove_unowned_path "$tree"
  fi
done

for path in "${NPM_CONFLICT_PATHS[@]}"; do
  if [[ -e "$path" || -L "$path" ]] && ! pacman -Qo "$path" >/dev/null 2>&1; then
    remove_unowned_path "$path"
    npm_touched=1
  fi
done

if (( npm_touched == 1 )) && pacman -Q npm >/dev/null 2>&1; then
  log_step "Repairing pacman-owned npm files after cleanup"
  sudo pacman -S --noconfirm npm
fi

if (( removed == 0 )); then
  log_step "No unowned conflicting npm-global paths found"
fi
