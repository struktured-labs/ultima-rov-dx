#!/usr/bin/env python3
"""Record the Cavern of Hatred entrance, exit and ladder transitions frame by frame.

Needs the save states written by `capture_screens.py` (save_states/{og,dx}_cavern_*.state;
DX states embed the WRAM runtime, so re-run capture_screens after every rebuild).
Runs the original ROM (DMG) and the DX ROM (CGB) headless from the same states and writes
to artifacts/:

  entry_sequence_dx.gif / entry_sequence_og.gif   whole entrance, every 2nd frame, 2x
  entry_strip_dx.png / entry_strip_og.png         every 6th frame, numbered
  entry_compare_strip.png                         key moments, original (top) vs DX
  cutscene_compare.png                            the entrance cutscene, 3x side by side
  title_card_compare.png                          the dungeon title card, 3x side by side
  exit_sequence_compare.png, ladder_sequence_compare.png

Usage: uv run --extra emu python scripts/capture_entry_sequence.py [--dx ROM] [--out DIR]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import capture_screens as C  # noqa: E402

STATES = ROOT / "save_states"


class Recorder:
    """PyBoy wrapper whose tick() keeps every frame plus LCDC/area, so nav() can drive it."""

    def __init__(self, pb):
        self.pb, self.memory = pb, pb.memory
        self.frames: list[Image.Image] = []
        self.log: list[tuple[int, int]] = []

    def tick(self, count: int = 1, render: bool = True) -> bool:
        for _ in range(count):
            self.pb.tick(1, True)
            self.frames.append(self.pb.screen.image.convert("RGB"))
            self.log.append((self.memory[0xFF40], self.memory[0xD12F]))
        return True

    def button_press(self, b):
        self.pb.button_press(b)

    def button_release(self, b):
        self.pb.button_release(b)


def record(rom: Path, state: Path, path: str, extra: int, pre: str | None = None) -> Recorder:
    from pyboy import PyBoy
    pb = PyBoy(str(rom), window="null", cgb=rom.suffix == ".gbc", sound_emulated=False)
    pb.set_emulation_speed(0)
    with open(state, "rb") as f:
        pb.load_state(f)
    if pre:
        C.nav(pb, pre)
    rec = Recorder(pb)
    C.nav(rec, path)
    rec.tick(extra)
    pb.stop(save=False)
    return rec


def events(rec: Recorder) -> dict[str, int]:
    lcdc = [l for l, _ in rec.log]
    n = len(lcdc)
    card = next(i for i in range(n - 20) if all(v == 0x8F for v in lcdc[i:i + 20]))
    cut = next(i for i in range(n) if lcdc[i] == 0x87)
    cut_end = next(i for i in range(cut, n) if lcdc[i] != 0x87)
    level = next(i for i in range(cut_end, n) if lcdc[i] & 0x80 and lcdc[i] != 0x80)
    return {"card": card, "cut": cut, "cut_end": cut_end, "level": level}


def strip(frames, idx, cols, labels=True) -> Image.Image:
    rows = (len(idx) + cols - 1) // cols
    img = Image.new("RGB", (cols * 164, rows * 156), "white")
    d = ImageDraw.Draw(img)
    for k, i in enumerate(idx):
        x, y = (k % cols) * 164, (k // cols) * 156
        img.paste(frames[i], (x, y + 12))
        if labels:
            d.text((x, y), str(i), fill=(200, 0, 0))
    return img


def pair(og: Image.Image, dx: Image.Image, scale: int, title: str) -> Image.Image:
    w, h = 160 * scale, 144 * scale
    img = Image.new("RGB", (2 * w + 3 * 8, h + 28), "white")
    d = ImageDraw.Draw(img)
    d.text((8, 6), f"{title}: original (DMG)", fill=(0, 0, 0))
    d.text((w + 16, 6), f"{title}: DX (CGB)", fill=(0, 0, 0))
    img.paste(og.resize((w, h), Image.NEAREST), (8, 22))
    img.paste(dx.resize((w, h), Image.NEAREST), (w + 16, 22))
    return img


def rows_compare(og, dx, og_idx, dx_idx, names, scale=1) -> Image.Image:
    w, h = 160 * scale, 144 * scale
    img = Image.new("RGB", (60 + len(names) * (w + 4), 2 * (h + 16) + 4), "white")
    d = ImageDraw.Draw(img)
    for r, (frames, idx, tag) in enumerate(((og, og_idx, "original"), (dx, dx_idx, "DX"))):
        y = r * (h + 16) + 14
        d.text((4, y + h // 2), tag, fill=(0, 0, 0))
        for c, (i, name) in enumerate(zip(idx, names)):
            x = 60 + c * (w + 4)
            if r == 0:
                d.text((x, 2), name, fill=(0, 0, 0))
            img.paste(frames[i].resize((w, h), Image.NEAREST), (x, y))
            d.text((x + 2, y + h - 11), str(i), fill=(200, 0, 0))
    return img


def gif(frames, path: Path, step=2, scale=2) -> None:
    seq = [f.resize((160 * scale, 144 * scale), Image.NEAREST) for f in frames[::step]]
    seq[0].save(path, save_all=True, append_images=seq[1:], duration=33, loop=0, optimize=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dx", type=Path, default=C.DX)
    ap.add_argument("--original", type=Path, default=C.ORIGINAL)
    ap.add_argument("--out", type=Path, default=ROOT / "artifacts")
    a = ap.parse_args()
    out = a.out
    out.mkdir(parents=True, exist_ok=True)
    roms = {"og": a.original, "dx": a.dx}

    ent = {k: record(r, STATES / f"{k}_cavern_approach.state", "U1", 480) for k, r in roms.items()}
    ev = {k: events(r) for k, r in ent.items()}
    for k, r in ent.items():
        e = ev[k]
        r.frames = r.frames[:e["level"] + 30]
        gif(r.frames, out / f"entry_sequence_{k}.gif")
        strip(r.frames, list(range(0, len(r.frames), 6)), 10).save(out / f"entry_strip_{k}.png")
        print(k, "frames", len(r.frames), e)

    def keys(e):
        return [4, e["card"] - 8, e["card"] + 30, e["cut"] - 4, e["cut"] + 60, e["cut"] + 150,
                e["cut"] + 225, e["cut_end"] + 6, e["level"] + 20]
    names = ["scroll", "blank", "title card", "blank", "cutscene", "hero walks", "into the cave", "blank", "level 1"]
    rows_compare(ent["og"].frames, ent["dx"].frames, keys(ev["og"]), keys(ev["dx"]), names).save(out / "entry_compare_strip.png")
    pair(ent["og"].frames[ev["og"]["cut"] + 150], ent["dx"].frames[ev["dx"]["cut"] + 150], 3,
         "Entrance cutscene").save(out / "cutscene_compare.png")
    pair(ent["og"].frames[ev["og"]["card"] + 30], ent["dx"].frames[ev["dx"]["card"] + 30], 3,
         "Dungeon title card").save(out / "title_card_compare.png")

    for name, path, pre in (("exit", "U2", None), ("ladder", "U5", "D7,R8,U1")):
        rec = {k: record(r, STATES / f"{k}_cavern_level1.state", path, 60, pre) for k, r in roms.items()}
        idx = {}
        for k, r in rec.items():
            off = next(i for i, (l, _) in enumerate(r.log) if l == 0)   # LCD off = the cut
            idx[k] = [off - 12, off - 4, off - 1, off + 3, off + 8, off + 12, off + 20]
        rows_compare(rec["og"].frames, rec["dx"].frames, idx["og"], idx["dx"],
                     ["walk", "step", "last frame", "off", "on", "+4", "+12"]).save(out / f"{name}_sequence_compare.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
