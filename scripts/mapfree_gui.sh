#!/usr/bin/env bash
# Launch MapFree GUI. By default uses placeholder (no OpenGL); set MAPFREE_OPENGL=1 for 3D viewer.
# Run from project root: ./scripts/mapfree_gui.sh

set -e
cd "$(dirname "$0")/.."

if [ -n "$VIRTUAL_ENV" ]; then
    exec python -m mapfree.app "$@"
else
    [ -d .venv ] && exec .venv/bin/python -m mapfree.app "$@"
    exec python3 -m mapfree.app "$@"
fi
