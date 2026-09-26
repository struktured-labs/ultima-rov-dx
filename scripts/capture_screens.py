#!/usr/bin/env python3
"""Capture before/after screenshots with headless PyBoy (no emulator window).

Runs the original ROM in DMG mode and the DX ROM in CGB mode through the
same scripted input route (title -> character select -> story -> overworld
next to Lord British's castle -> throne room) and writes:

  artifacts/<scene>_dmg.png, artifacts/<scene>_dx.png   (native 160x144)
  artifacts/<scene>_compare.png                          (side by side, 3x)
  artifacts/contact_sheet.png                            (all scenes)

Usage: uv run --extra emu python scripts/capture_screens.py [--dx ROM] [--out DIR]
The two runs drift by a few frames (the DX build spends time recomputing
attributes at LCD-on), so paired shots show the same scene, not the same frame.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "rom" / "Ultima - Runes of Virtue (USA).gb"
DX = ROOT / "rom" / "working" / "ultima_rov_dx.gbc"

# (scene name, actions before the shot). Action = (button or None, hold, after)
ROUTE: list[tuple[str, list[tuple[str | None, int, int]]]] = [
    ("title_castle", [(None, 0, 520)]),
    ("title_logo", [(None, 0, 260)]),
    ("credits", [(None, 0, 120)]),
    ("character_select", [("start", 6, 54)] + [("a", 6, 54)] * 6),
    ("story", [("start", 6, 54)] * 3),
    ("overworld", [("a", 6, 90)] * 15),
    ("castle_throne_room", [(None, 0, 120)] + [("up", 35, 10)] * 3 + [(None, 0, 40)]),
]


def run(rom: Path, cgb: bool) -> dict:
    from pyboy import PyBoy

    pb = PyBoy(str(rom), window="null", cgb=cgb, sound_emulated=False)
    pb.set_emulation_speed(0)
    shots = {}
    try:
        for scene, actions in ROUTE:
            for button, hold, after in actions:
                if button:
                    pb.button_press(button)
                    pb.tick(hold, True)
                    pb.button_release(button)
                pb.tick(max(after, 1), True)
            shots[scene] = pb.screen.image.convert("RGB").copy()
    finally:
        pb.stop(save=False)
    return shots


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--original", type=Path, default=ORIGINAL)
    ap.add_argument("--dx", type=Path, default=DX)
    ap.add_argument("--out", type=Path, default=ROOT / "artifacts")
    args = ap.parse_args()
    for p in (args.original, args.dx):
        if not p.is_file():
            print(f"missing ROM: {p}", file=sys.stderr)
            return 66
    from PIL import Image

    args.out.mkdir(parents=True, exist_ok=True)
    before, after = run(args.original, False), run(args.dx, True)
    rows = []
    for scene, _ in ROUTE:
        b, a = before[scene], after[scene]
        b.save(args.out / f"{scene}_dmg.png")
        a.save(args.out / f"{scene}_dx.png")
        pair = Image.new("RGB", (330, 144), "white")
        pair.paste(b, (0, 0))
        pair.paste(a, (170, 0))
        pair.resize((990, 432), Image.NEAREST).save(args.out / f"{scene}_compare.png")
        rows.append(pair)
    sheet = Image.new("RGB", (330 * 2 + 10, (144 + 6) * ((len(rows) + 1) // 2)), "white")
    for i, pair in enumerate(rows):
        sheet.paste(pair, ((i % 2) * 340, (i // 2) * 150))
    sheet.resize((sheet.width * 2, sheet.height * 2), Image.NEAREST).save(args.out / "contact_sheet.png")
    print(f"wrote {len(rows)} scene pairs to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
