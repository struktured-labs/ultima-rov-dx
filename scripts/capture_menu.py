#!/usr/bin/env python3
"""Start-menu and side-panel comparison shots (headless PyBoy, original vs DX).

Needs the cavern save states written by capture_screens.py (same build!):
  save_states/{og,dx}_cavern_level1.state

From that state it opens the start menu (START) in both builds and writes:

  save_states/{og,dx}_menu.state          the menu with the real inventory
  artifacts/menu_{dmg,dx}.png             that menu, native 160x144
  artifacts/menu_compare.png              rows: real inventory, items $00-$1F,
                                          items $20-$3F, after equipping (A/B
                                          swapped inside the menu), back on the
                                          map; columns: original | DX, plus
                                          artifacts/mister_menu_before.png (the
                                          MiSTer shot of the pre-menu-work beta)
                                          when present
  artifacts/side_panel_compare.png        the right-hand panel (A/B items, gold,
                                          hearts, stars) cropped from the map
                                          scenes of capture_screens.py, the menu
                                          and the map after equipping, original
                                          above DX, 3x

Usage: uv run --extra emu python scripts/capture_menu.py [--dx ROM]
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "rom" / "Ultima - Runes of Virtue (USA).gb"
DX = ROOT / "rom" / "working" / "ultima_rov_dx.gbc"
STATES = ROOT / "save_states"
ART = ROOT / "artifacts"
PANEL_SCENES = ["overworld", "castle_throne_room", "lord_british_dialog", "cavern_level1", "cavern_level2_arrows"]


def press(pb, button: str, after: int = 30) -> None:
    pb.button_press(button)
    pb.tick(6, True)
    pb.button_release(button)
    pb.tick(after, True)


def shots_for(rom: Path, cgb: bool) -> list:
    from pyboy import PyBoy

    tag = "dx" if cgb else "og"
    pb = PyBoy(str(rom), window="null", cgb=cgb, sound_emulated=False)
    pb.set_emulation_speed(0)
    mem = pb.memory
    out = []
    try:
        with open(STATES / f"{tag}_cavern_level1.state", "rb") as f:
            pb.load_state(f)
        press(pb, "start", 90)
        out.append(pb.screen.image.convert("RGB").copy())
        with open(STATES / f"{tag}_menu.state", "wb") as f:
            pb.save_state(f)
        for first in (0x00, 0x20):
            press(pb, "start", 90)              # back to the map, change the bag, reopen
            for i in range(32):
                mem[0xD100 + i] = first + i
            press(pb, "start", 90)
            out.append(pb.screen.image.convert("RGB").copy())
        for button in ("right", "right", "down"):
            press(pb, button, 15)                # cursor to slot 10
        press(pb, "a", 40)                       # swap with the A item
        press(pb, "left", 15)
        press(pb, "b", 40)                       # slot 9 with the B item
        out.append(pb.screen.image.convert("RGB").copy())
        press(pb, "start", 120)
        out.append(pb.screen.image.convert("RGB").copy())
    finally:
        pb.stop(save=False)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--original", type=Path, default=ORIGINAL)
    ap.add_argument("--dx", type=Path, default=DX)
    args = ap.parse_args()
    for p in (args.original, args.dx, STATES / "og_cavern_level1.state", STATES / "dx_cavern_level1.state"):
        if not p.is_file():
            print(f"missing: {p} (run capture_screens.py first)", file=sys.stderr)
            return 66
    from PIL import Image

    og, dx = shots_for(args.original, False), shots_for(args.dx, True)
    og[0].save(ART / "menu_dmg.png")
    dx[0].save(ART / "menu_dx.png")
    mister = ART / "mister_menu_before.png"
    cols = 3 if mister.is_file() else 2
    sheet = Image.new("RGB", (cols * 170 - 10, len(og) * 150 - 6), "white")
    for r, (a, b) in enumerate(zip(og, dx)):
        sheet.paste(a, (0, r * 150))
        sheet.paste(b, (170, r * 150))
    if cols == 3:
        sheet.paste(Image.open(mister).convert("RGB").resize((160, 144)), (340, 0))
    sheet.resize((sheet.width * 3, sheet.height * 3), Image.NEAREST).save(ART / "menu_compare.png")

    crops = []
    for scene in PANEL_SCENES:
        pair = [ART / f"{scene}_{k}.png" for k in ("dmg", "dx")]
        if all(p.is_file() for p in pair):
            crops.append([Image.open(p).convert("RGB").crop((144, 0, 160, 144)) for p in pair])
    crops.append([og[0].crop((144, 0, 160, 144)), dx[0].crop((144, 0, 160, 144))])
    crops.append([og[4].crop((144, 0, 160, 144)), dx[4].crop((144, 0, 160, 144))])   # map after equipping
    panel = Image.new("RGB", (len(crops) * 22 - 6, 2 * 150 - 6), "white")
    for i, (a, b) in enumerate(crops):
        panel.paste(a, (i * 22, 0))
        panel.paste(b, (i * 22, 150))
    panel.resize((panel.width * 3, panel.height * 3), Image.NEAREST).save(ART / "side_panel_compare.png")
    print(f"wrote {ART / 'menu_compare.png'}, {ART / 'side_panel_compare.png'}, {STATES}/{{og,dx}}_menu.state")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
