#!/usr/bin/env bash
set -euo pipefail

PACKAGE_CHECKOUT="$HOME/.pi/agent/git/github.com/mortenvp/agent-stuff"
REMOTE_URL="https://github.com/mortenvp/agent-stuff.git"
REMOTE_REF="refs/heads/main"

if ! command -v pi >/dev/null 2>&1 || ! command -v git >/dev/null 2>&1; then
  exit 0
fi

if ! git -C "$PACKAGE_CHECKOUT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  exit 0
fi

if ! local_commit=$(git -C "$PACKAGE_CHECKOUT" rev-parse HEAD 2>/dev/null); then
  exit 0
fi

if ! remote_commit=$(git ls-remote "$REMOTE_URL" "$REMOTE_REF" 2>/dev/null | awk 'NR == 1 { print $1 }'); then
  exit 0
fi

if [[ -z "$remote_commit" || "$local_commit" == "$remote_commit" ]]; then
  exit 0
fi

printf 'pi-agent-stuff %.7s -> %.7s\n' "$local_commit" "$remote_commit"
