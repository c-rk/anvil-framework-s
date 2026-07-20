#!/bin/sh
# One-command launcher for the Anvil workbench (POSIX).
#   ./start_anvil.sh            (chmod +x start_anvil.sh first if needed)
set -e
cd "$(dirname "$0")"

if command -v python3 >/dev/null 2>&1; then
    PY=python3
elif command -v python >/dev/null 2>&1; then
    PY=python
else
    echo "[anvil] ERROR: Python not found. Install Python 3.10+ first." >&2
    exit 1
fi

exec "$PY" start_anvil.py "$@"
