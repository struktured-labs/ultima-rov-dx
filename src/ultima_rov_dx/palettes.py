"""Palette YAML loading and CGB CRAM encoding.

Same YAML schema as penta-dragon-dx (`bg_palettes` / `obj_palettes`, each an
ordered mapping of ``Name: {colors: [4 x BGR555 hex]}``). Colors are
either "#RRGGBB" or BGR555 hex strings: 0bBBBBBGGGGGRRRRR, e.g. 7FFF white,
001F red, 03E0 green, 7C00 blue, 0000 black.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

PALETTES_PER_KIND = 8
COLORS_PER_PALETTE = 4


def load(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top level must be a mapping")
    return data


def bgr555(color: str) -> int:
    text = str(color).strip().upper()
    if text.startswith("#"):
        if len(text) != 7 or any(c not in "0123456789ABCDEF" for c in text[1:]):
            raise ValueError(f"invalid RGB color {color!r}; expected '#RRGGBB'")
        return rgb888_to_bgr555(int(text[1:3], 16), int(text[3:5], 16), int(text[5:7], 16))
    if len(text) != 4 or any(c not in "0123456789ABCDEF" for c in text):
        raise ValueError(f"invalid BGR555 color {color!r}; expected 4 hex digits like '7FFF'")
    value = int(text, 16)
    if value > 0x7FFF:
        raise ValueError(f"BGR555 color {color!r} sets bit 15")
    return value


def rgb888_to_bgr555(r: int, g: int, b: int) -> int:
    return ((b >> 3) << 10) | ((g >> 3) << 5) | (r >> 3)


def _encode_group(group: dict[str, Any], kind: str) -> tuple[bytes, list[str]]:
    if not isinstance(group, dict):
        raise ValueError(f"{kind} must be a mapping of name -> palette")
    if len(group) != PALETTES_PER_KIND:
        raise ValueError(f"{kind} must define exactly {PALETTES_PER_KIND} palettes (got {len(group)})")
    out = bytearray()
    names: list[str] = []
    for name, entry in group.items():
        colors = entry.get("colors") if isinstance(entry, dict) else entry
        if not isinstance(colors, list) or len(colors) != COLORS_PER_PALETTE:
            raise ValueError(f"{kind}.{name} must have exactly {COLORS_PER_PALETTE} colors")
        for color in colors:
            out += bgr555(color).to_bytes(2, "little")
        names.append(str(name))
    return bytes(out), names


def encode(data: dict[str, Any]) -> dict[str, Any]:
    """Return {'bg': 64 bytes, 'obj': 64 bytes, 'bg_names': [...], 'obj_names': [...]}."""

    bg, bg_names = _encode_group(data.get("bg_palettes"), "bg_palettes")
    obj, obj_names = _encode_group(data.get("obj_palettes"), "obj_palettes")
    return {"bg": bg, "obj": obj, "bg_names": bg_names, "obj_names": obj_names}


def names(data: dict[str, Any], kind: str) -> list[str]:
    """Palette names in hardware order for ``bg_palettes`` / ``obj_palettes``."""

    return [str(n) for n in (data.get(kind) or {})]
