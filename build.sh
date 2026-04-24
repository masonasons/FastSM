#!/bin/bash
# Build script for FastSM using PyInstaller.
#
# Works on Linux and macOS. On Linux we prefer python3.13 because that's the
# version wxPython publishes Linux wheels for; fall through to python3 if 3.13
# isn't installed.

set -e

PY=""
for candidate in python3.13 python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
        PY="$candidate"
        break
    fi
done

if [ -z "$PY" ]; then
    echo "No Python 3 interpreter found on PATH." >&2
    exit 1
fi

echo "========================================"
echo "Building FastSM with PyInstaller ($PY)"
echo "========================================"
echo

if ! "$PY" -c "import PyInstaller" >/dev/null 2>&1; then
    echo "PyInstaller is not installed. Installing..."
    PIP_ARGS=""
    # Linux system pythons are usually PEP 668 managed.
    if [ "$(uname -s)" = "Linux" ]; then
        PIP_ARGS="--break-system-packages"
    fi
    if ! "$PY" -m pip install $PIP_ARGS pyinstaller; then
        echo "Failed to install PyInstaller" >&2
        exit 1
    fi
fi

"$PY" build.py

echo
echo "Build complete."
