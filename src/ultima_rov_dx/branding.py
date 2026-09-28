"""DX title-logo branding: a "DX" plate beside the ankh coin and a credit
line under "Runes of Virtue" (palettes/branding.yaml).

Composed at build time. The credit uses the game's own capital font, read
from the verified ROM (never stored in the repo): C-Z at 0xE0C0 + 16*i,
A/B from the side-panel glyphs at 0xCAA0/0xCAB0 (tile-map dumps in
tmp/probe/font.py). The plate is original art below.
"""

from __future__ import annotations

from typing import Any

FONT_C_Z = 0xE0C0
FONT_A, FONT_B = 0xCAA0, 0xCAB0
SCREEN_W = 160

# 11x12 letters, 2 px strokes; drawn light with a red drop shadow.
_D = ["11111111000", "11111111100", "11000000110", "11000000011", "11000000011", "11000000011",
      "11000000011", "11000000011", "11000000011", "11000000110", "11111111100", "11111111000"]
_X = ["11000000011", "11100000111", "01110001110", "00111011100", "00011111000", "00001110000",
      "00001110000", "00011111000", "00111011100", "01110001110", "11100000111", "11000000011"]


class BrandingError(Exception):
    pass


def _glyph(rom: bytes, ch: str) -> list[list[int]]:
    if ch == "A":
        off = FONT_A
    elif ch == "B":
        off = FONT_B
    elif "C" <= ch <= "Z":
        off = FONT_C_Z + 16 * (ord(ch) - ord("C"))
    else:
        raise BrandingError(f"no glyph for {ch!r} (capitals and spaces only)")
    b = rom[off:off + 16]
    return [[1 if ((b[2 * y] | b[2 * y + 1]) >> (7 - x)) & 1 else 0 for x in range(8)] for y in range(8)]


def _tiles(canvas: list[list[int]], cols: int, rows: int) -> list[bytes]:
    out = []
    for r in range(rows):
        for c in range(cols):
            t = bytearray()
            for y in range(8):
                lo = hi = 0
                for x in range(8):
                    v = canvas[r * 8 + y][c * 8 + x]
                    lo |= (v & 1) << (7 - x)
                    hi |= (v >> 1) << (7 - x)
                t += bytes([lo, hi])
            out.append(bytes(t))
    return out


def credit_canvas(rom: bytes, text: str, ink: int, glow: int, bg: int) -> list[list[int]]:
    """One 8 px text row across the screen, centred to the pixel, glow around the ink."""
    w = 8 * len(text)
    if w > SCREEN_W:
        raise BrandingError(f"credit {text!r} wider than the screen")
    x0 = (SCREEN_W - w) // 2
    canvas = [[bg] * SCREEN_W for _ in range(8)]
    for i, ch in enumerate(text):
        if ch == " ":
            continue
        g = _glyph(rom, ch)
        for y in range(8):
            for x in range(8):
                if g[y][x]:
                    canvas[y][x0 + 8 * i + x] = ink
    for y in range(8):
        for x in range(SCREEN_W):
            if canvas[y][x] == bg and any(0 <= y + dy < 8 and 0 <= x + dx < SCREEN_W and canvas[y + dy][x + dx] == ink
                                          for dy in (-1, 0, 1) for dx in (-1, 0, 1)):
                canvas[y][x] = glow
    return canvas


def plate_canvas(border: int, fill: int, letter: int, shadow: int) -> list[list[int]]:
    """32x16 "DX" plate (4x2 tiles)."""
    p = [[border if x in (0, 31) or y in (0, 15) else fill for x in range(32)] for y in range(16)]
    for pat, ox in ((_D, 3), (_X, 17)):
        for y, row in enumerate(pat):
            for x, c in enumerate(row):
                if c == "1" and p[2 + y + 1][ox + x + 1] == fill:
                    p[2 + y + 1][ox + x + 1] = shadow
        for y, row in enumerate(pat):
            for x, c in enumerate(row):
                if c == "1":
                    p[2 + y][ox + x] = letter
    return p


def build(rom: bytes, spec: dict[str, Any]) -> tuple[bytes, list[tuple[int, int, int, str]]]:
    """Returns (tile data for tiles first_tile.., cells (row, col, tile id, palette name))."""
    first = int(spec.get("first_tile", 0xA0))
    uniq: list[bytes] = []
    cells: list[tuple[int, int, int, str]] = []

    def tid(t: bytes) -> int:
        if t not in uniq:
            uniq.append(t)
        return first + uniq.index(t)

    cr = spec["credit"]
    sh = cr["shades"]
    canvas = credit_canvas(rom, cr["text"], sh["ink"], sh["glow"], sh["background"])
    blank = _tiles([[sh["background"]] * 8 for _ in range(8)], 1, 1)[0]
    for c, t in enumerate(_tiles(canvas, 20, 1)):
        if t != blank:
            cells.append((cr["row"], c, tid(t), cr["palette"]))
    pl = spec["plate"]
    sh = pl["shades"]
    for i, t in enumerate(_tiles(plate_canvas(sh["border"], sh["fill"], sh["letter"], sh["shadow"]), 4, 2)):
        cells.append((pl["row"] + i // 4, pl["col"] + i % 4, tid(t), pl["palette"]))
    if first + len(uniq) > 0x100:
        raise BrandingError(f"{len(uniq)} branding tiles do not fit from {first:#x}")
    return b"".join(uniq), cells
