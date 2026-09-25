#!/usr/bin/env bash
# Launch mgba-qt for human play through the project single-flight guard.
# Usage: scripts/launch_mgba.sh [rom_path] [extra mGBA args...]
#
# Adapted from penta-dragon-dx: that launcher hard-codes DISPLAY=:0 and
# NVIDIA/KDE-Wayland variables. Here the current DISPLAY is kept (falls back
# to :0) and the NVIDIA settings are opt-in via ROV_MGBA_NVIDIA=1.
set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
ROM="${1:-rom/working/ultima_rov_dx.gb}"
GUARDED_MGBA="$PROJECT_DIR/scripts/mgba-qt-singleflight"
if [[ "$#" -gt 0 ]]; then
    shift
fi

if [[ "$ROM" != /* ]]; then
    ROM="$PROJECT_DIR/$ROM"
fi

if [ ! -f "$ROM" ]; then
    echo "ROM not found: $ROM" >&2
    echo "Build it first: uv run python scripts/build_dx.py" >&2
    exit 1
fi

# Ensure OpenGL display driver in config (same as penta-dragon-dx)
QTINI="$HOME/.config/mgba/qt.ini"
if [ -f "$QTINI" ]; then
    sed -i 's/^displayDriver=.*/displayDriver=1/' "$QTINI"
fi

export DISPLAY="${DISPLAY:-:0}"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"
if [[ "${ROV_MGBA_NVIDIA:-0}" == "1" ]]; then
    export __GLX_VENDOR_LIBRARY_NAME=nvidia
    export VK_DRIVER_FILES=/usr/share/vulkan/icd.d/nvidia_icd.json
fi

# Stay alive as the emulator's guardian. If this launcher is interrupted, the
# wrapper's parent-death signal terminates the exact emulator it owns.
echo "Starting guarded mGBA (a concurrent emulator will fail closed)..."
exec "$GUARDED_MGBA" "$ROM" "$@"
