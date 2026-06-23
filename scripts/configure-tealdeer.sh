#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=scripts/logging.sh
source "$SCRIPT_DIR/logging.sh"

if ! command -v tldr >/dev/null 2>&1; then
  log_step "tldr not found; skipping tealdeer setup"
  exit 0
fi

CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/tealdeer"
CONFIG_FILE="$CONFIG_DIR/config.toml"

mkdir -p "$CONFIG_DIR"

if [[ ! -f "$CONFIG_FILE" ]]; then
  log_step "Seeding tealdeer config"
  tldr --seed-config >/dev/null 2>&1 || true
fi

if [[ ! -f "$CONFIG_FILE" ]]; then
  cat >"$CONFIG_FILE" <<'EOF'
[updates]
auto_update = true
EOF
  log_step "Created tealdeer config at $CONFIG_FILE"
else
  tmp_file=$(mktemp)
  awk '
    BEGIN {
      in_updates = 0
      saw_updates = 0
      saw_auto = 0
    }

    /^[[:space:]]*\[[^]]+\][[:space:]]*$/ {
      if (in_updates && !saw_auto) {
        print "auto_update = true"
        saw_auto = 1
      }

      if ($0 ~ /^[[:space:]]*\[updates\][[:space:]]*$/) {
        in_updates = 1
        saw_updates = 1
      } else {
        in_updates = 0
      }

      print
      next
    }

    {
      if (in_updates && $0 ~ /^[[:space:]]*auto_update[[:space:]]*=/) {
        print "auto_update = true"
        saw_auto = 1
        next
      }

      print
    }

    END {
      if (in_updates && !saw_auto) {
        print "auto_update = true"
      }

      if (!saw_updates) {
        print ""
        print "[updates]"
        print "auto_update = true"
      }
    }
  ' "$CONFIG_FILE" >"$tmp_file"

  install -m 644 "$tmp_file" "$CONFIG_FILE"
  rm -f "$tmp_file"
  log_step "Enabled tealdeer auto_update in $CONFIG_FILE"
fi

log_step "Updating tldr page cache"
tldr --update >/dev/null
