#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=scripts/logging.sh
source "$SCRIPT_DIR/logging.sh"

WARP_CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/warp-terminal"
WARP_SETTINGS="$WARP_CONFIG_DIR/settings.toml"
VOICE_TOGGLE_KEY='super_right'

mkdir -p "$WARP_CONFIG_DIR"
tmp_file=$(mktemp "$WARP_CONFIG_DIR/settings.toml.XXXXXX")
trap 'rm -f "$tmp_file"' EXIT

if [[ -f "$WARP_SETTINGS" ]]; then
  awk -v toggle_key="$VOICE_TOGGLE_KEY" '
    function write_setting() {
      print "voice_input_toggle_key = \"" toggle_key "\""
    }

    /^\[[[:space:]]*agents\.voice[[:space:]]*\][[:space:]]*(#.*)?$/ {
      if (in_voice && !found_key) {
        write_setting()
      }
      in_voice = 1
      found_section = 1
      print
      next
    }

    /^\[/ {
      if (in_voice && !found_key) {
        write_setting()
        found_key = 1
      }
      in_voice = 0
    }

    in_voice && /^[[:space:]]*voice_input_toggle_key[[:space:]]*=/ {
      write_setting()
      found_key = 1
      next
    }

    { print }

    END {
      if (!found_section) {
        if (NR > 0) print ""
        print "[agents.voice]"
        write_setting()
      } else if (in_voice && !found_key) {
        write_setting()
      }
    }
  ' "$WARP_SETTINGS" >"$tmp_file"
else
  cat >"$tmp_file" <<EOF
[agents.voice]
voice_input_toggle_key = "$VOICE_TOGGLE_KEY"
EOF
fi

chmod 600 "$tmp_file"
mv "$tmp_file" "$WARP_SETTINGS"
trap - EXIT

log_step "Configured Warp voice input toggle to Right Super in $WARP_SETTINGS"
