#!/usr/bin/env python3
"""Capture before/after screenshots with headless PyBoy (no emulator window).

Runs the original ROM in DMG mode and the DX ROM in CGB mode through the
same scripted input route (title -> character select -> story -> overworld
next to Lord British's castle -> throne room -> back out -> Cavern of
Hatred, the dungeon due north of the castle: level 1 (area $18) and level 2
(area $19) and writes:

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

# (scene name, actions before the shot). Action = (button or None, hold, after),
# or ("nav", "R1,U2,...", 0): walk whole map cells, watching the player cell
# at $FF91 (high nibble = row, low = column) and the area id at $D12F.
ROUTE: list[tuple[str, list[tuple[str | None, int | str, int]]]] = [
    ("title_castle", [(None, 0, 520)]),
    ("title_logo", [(None, 0, 260)]),
    ("credits", [(None, 0, 120)]),
    # press START until the character-select screen is switched on (bank3
    # LCD-on at $78F8), so both runs pick the same champion in lockstep
    ("character_select", [("until", "start", 0)] + [("a", 6, 54)] * 6),
    ("story", [("start", 6, 54)] * 3),
    ("overworld", [("a", 6, 90)] * 15),
    ("castle_throne_room", [(None, 0, 120)] + [("up", 35, 10)] * 3 + [(None, 0, 40)]),
    ("lord_british_dialog", [("up", 30, 60)]),           # walk into Lord British: text screen
    ("after_dialog", [("a", 6, 60)]),                     # map restored ($03A3)
]
# Second pass (fresh boot, same inputs up to the overworld): from the start
# position south of the castle, go around it to the cave mouth due north.
CAVERN_ROUTE = ROUTE[:6] + [
    ("cavern_approach", [("nav", "R1,U2,L1", 0), (None, 0, 20)]),     # one cell below the cave mouth
    ("cavern_entrance", [("nav", "U2", 0), (None, 0, 420)]),
    ("cavern_level1", [("nav", "D2", 0), (None, 0, 30)]),
    ("cavern_level2", [("nav", "D7,R8,U1,U5", 0), (None, 0, 300)]),
    ("cavern_level2_arrows", [("nav", "L4", 0), (None, 0, 20)]),
    ("cavern_level3", [("nav", "R1,D5,R2,D1", 0), (None, 0, 300)]),   # exit at the south-east room
]


CHARACTER_SELECT_LCD_ON = 0x78F8   # bank 3: `ldh [rLCDC],a` (DX: rst $28) of the champion screen
DIRS = {"R": "right", "L": "left", "D": "down", "U": "up"}


def settle(pb, limit: int = 60) -> None:
    """Let the current step finish: wait until scroll and player sprite stop moving."""
    mem = pb.memory
    last, still = None, 0
    for _ in range(limit):
        pb.tick(1, True)
        now = (mem[0xFF42], mem[0xFF43], mem[0xFE00], mem[0xFE01])
        still = still + 1 if now == last else 0
        last = now
        if still >= 3:
            return


def nav(pb, path: str) -> None:
    mem = pb.memory
    for move in path.split(","):
        button = DIRS[move[0]]
        for _ in range(int(move[1:])):
            start, area = mem[0xFF91], mem[0xD12F]
            for _attempt in range(30):
                t = 0
                pb.button_press(button)
                pos = (mem[0xFF42], mem[0xFF43], mem[0xFE00], mem[0xFE01])
                # release as soon as the step starts (cell, scroll or sprite moves)
                while (mem[0xFF91] == start and mem[0xD12F] == area and t < 120
                       and (mem[0xFF42], mem[0xFF43], mem[0xFE00], mem[0xFE01]) == pos):
                    pb.tick(1, True)
                    t += 1
                pb.button_release(button)
                settle(pb)
                if mem[0xFF91] != start or mem[0xD12F] != area:
                    break
                if t < 120:
                    continue          # moved on screen without changing cell yet: press again
                pb.button_press("b")          # something in the way: attack, retry
                pb.tick(6, True)
                pb.button_release("b")
                pb.tick(60, True)
            if mem[0xD12F] != area:
                return                        # area changed (door, ladder, cave mouth)


def run(rom: Path, cgb: bool, states: Path | None = None) -> dict:
    shots = run_route(rom, cgb, ROUTE, states)
    shots.update(run_route(rom, cgb, CAVERN_ROUTE, states))
    return shots


def run_route(rom: Path, cgb: bool, route, states: Path | None) -> dict:
    from pyboy import PyBoy

    pb = PyBoy(str(rom), window="null", cgb=cgb, sound_emulated=False)
    pb.set_emulation_speed(0)
    hit: list[int] = []
    pb.hook_register(3, CHARACTER_SELECT_LCD_ON, lambda _ctx: hit.append(1), None)
    shots = {}
    try:
        for scene, actions in route:
            for button, hold, after in actions:
                if button == "nav":
                    nav(pb, hold)
                    continue
                if button == "until":
                    hit.clear()
                    for _ in range(60):
                        pb.button_press(hold)
                        pb.tick(6, True)
                        pb.button_release(hold)
                        for _ in range(54):
                            pb.tick(1, True)
                            if hit:
                                break
                        if hit:
                            break
                    pb.tick(54, True)
                    continue
                if button:
                    pb.button_press(button)
                    pb.tick(hold, True)
                    pb.button_release(button)
                pb.tick(max(after, 1), True)
            shots[scene] = pb.screen.image.convert("RGB").copy()
            shots[scene + "@area"] = pb.memory[0xD12F]
            if states is not None and scene.startswith("cavern"):
                states.mkdir(parents=True, exist_ok=True)
                with open(states / f"{'dx' if cgb else 'og'}_{scene}.state", "wb") as f:
                    pb.save_state(f)
    finally:
        pb.stop(save=False)
    return shots


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--original", type=Path, default=ORIGINAL)
    ap.add_argument("--dx", type=Path, default=DX)
    ap.add_argument("--out", type=Path, default=ROOT / "artifacts")
    ap.add_argument("--states", type=Path, default=ROOT / "save_states",
                    help="write PyBoy save states of the cavern scenes here (gitignored)")
    args = ap.parse_args()
    for p in (args.original, args.dx):
        if not p.is_file():
            print(f"missing ROM: {p}", file=sys.stderr)
            return 66
    from PIL import Image

    args.out.mkdir(parents=True, exist_ok=True)
    before, after = run(args.original, False, args.states), run(args.dx, True, args.states)
    rows = []
    scenes = [sc for sc, _ in ROUTE] + [sc for sc, _ in CAVERN_ROUTE if sc.startswith("cavern")]
    for scene in scenes:
        b, a = before[scene], after[scene]
        if before[scene + "@area"] != after[scene + "@area"]:
            print(f"warning: {scene}: original in area {before[scene + '@area']:#x}, DX in {after[scene + '@area']:#x}")
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
