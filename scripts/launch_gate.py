#!/usr/bin/env python3
"""Pre-launch gate: verify a ROM boots to a non-blank screen before headed play.

Usage:
    uv run --extra emu python scripts/launch_gate.py rom/working/ultima_rov_dx.gb

Exit 0 = screen shows content after N frames (or PyBoy unavailable -> skipped),
     1 = blank/white screen (typical of a CGB-flagged ROM with no palettes loaded),
     2 = harness error / ROM missing.

Adapted from penta-dragon-dx's launch_gate.py. Penta's boot check polled a
game-specific RAM byte (D880); this version is game-agnostic and only looks
at pixels. TODO(RE): add a Runes-of-Virtue title-screen state check once the
scene variable is known (src/ultima_rov_dx/game_layout.py SCENE_STATE_ADDR).
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


def check_rom(rom: Path, frames: int, min_content: float) -> int:
    try:
        from pyboy import PyBoy
    except ImportError:
        print("LAUNCH GATE: pyboy not available (uv sync --extra emu); skipping verification")
        return 0
    import numpy as np

    if not rom.is_file():
        print(f"LAUNCH GATE FAILED: ROM not found at {rom}")
        return 2
    pb = PyBoy(str(rom), window="null", cgb=True, sound_emulated=False)
    try:
        pb.set_emulation_speed(0)
        pb.tick(frames, True)
        pixels = np.array(pb.screen.image.convert("RGB"))
    finally:
        pb.stop(save=False)
    non_white = float(np.mean(np.any(pixels < 240, axis=2)))
    print(f"LAUNCH GATE: {non_white:.1%} non-white pixels after {frames} frames")
    if non_white < min_content:
        print("LAUNCH GATE FAILED: screen is blank")
        return 1
    print("LAUNCH GATE PASSED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--frames", type=int, default=600)
    parser.add_argument("--min-content", type=float, default=0.05)
    args = parser.parse_args()
    try:
        return check_rom(args.rom, args.frames, args.min_content)
    except Exception as exc:  # harness error
        print(f"LAUNCH GATE HARNESS ERROR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
