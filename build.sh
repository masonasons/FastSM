#!/bin/bash
set -euo pipefail

# Linux build helper. Defaults to a low parallelism level so dependency
# compilation does not consume all CPU cores.
PYTHON_BIN="${PYTHON_BIN:-python3}"
FASTSM_BUILD_JOBS="${FASTSM_BUILD_JOBS:-2}"

echo "========================================"
echo "Building FastSM for Linux"
echo "========================================"
echo "Python: ${PYTHON_BIN}"
echo "Build jobs: ${FASTSM_BUILD_JOBS}"
echo

# Cap parallel build workers for dependency builds.
export CMAKE_BUILD_PARALLEL_LEVEL="${CMAKE_BUILD_PARALLEL_LEVEL:-$FASTSM_BUILD_JOBS}"
export MAX_JOBS="${MAX_JOBS:-$FASTSM_BUILD_JOBS}"
export NPY_NUM_BUILD_JOBS="${NPY_NUM_BUILD_JOBS:-$FASTSM_BUILD_JOBS}"
export MAKEFLAGS="${MAKEFLAGS:--j$FASTSM_BUILD_JOBS}"

# Install PyInstaller if missing.
if ! "${PYTHON_BIN}" -m PyInstaller --version > /dev/null 2>&1; then
	echo "PyInstaller is not installed. Installing..."
	"${PYTHON_BIN}" -m pip install pyinstaller
fi

# Install/update runtime dependencies unless explicitly skipped.
if [ "${SKIP_DEPS:-0}" != "1" ]; then
	echo "Installing Linux dependencies..."
	if [ -f requirements-linux.txt ]; then
		"${PYTHON_BIN}" -m pip install -r requirements.txt -r requirements-linux.txt
	else
		"${PYTHON_BIN}" -m pip install -r requirements.txt
	fi
fi

# Run platform-aware build script (now supports Linux).
"${PYTHON_BIN}" build.py

echo
echo "Build complete."
