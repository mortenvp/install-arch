#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=scripts/logging.sh
source "$SCRIPT_DIR/logging.sh"

GDBINIT_TARGET="$HOME/.gdbinit"
BLOCK_START="# >>> install-arch gdb pretty printers >>>"
BLOCK_END="# <<< install-arch gdb pretty printers <<<"

tmp_file=$(mktemp)

cleanup() {
  rm -f "$tmp_file"
}
trap cleanup EXIT

if [[ -f "$GDBINIT_TARGET" ]]; then
  awk -v start="$BLOCK_START" -v end="$BLOCK_END" '
    $0 == start { in_block = 1; next }
    $0 == end { in_block = 0; next }
    !in_block { print }
  ' "$GDBINIT_TARGET" >"$tmp_file"
fi

if [[ -s "$tmp_file" ]]; then
  printf '\n' >>"$tmp_file"
fi

cat <<EOF >>"$tmp_file"
$BLOCK_START
set auto-load python-scripts on
skip -rfu ^std::
skip -rfu ^__gnu_cxx::
skip -gfi /usr/include/*
skip -gfi /usr/lib/*
python
import glob
import os
import sys

python_dirs = sorted(glob.glob("/usr/share/gcc-*/python"))
for path in python_dirs:
    if os.path.isdir(path) and path not in sys.path:
        sys.path.insert(0, path)

try:
    from libstdcxx.v6.printers import register_libstdcxx_printers
    register_libstdcxx_printers(None)
except Exception as error:
    gdb.write("install-arch: libstdc++ pretty printers unavailable: {}\\n".format(error))
end
$BLOCK_END
EOF

install -m 644 "$tmp_file" "$GDBINIT_TARGET"
log_step "Configured global GDB pretty printers in $GDBINIT_TARGET"
