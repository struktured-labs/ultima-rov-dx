"""Build the CGB colorization patch for Ultima: Runes of Virtue.

Pure function of (original ROM bytes, palette YAML data, category YAML
data). Assembles ``asm/dx.asm`` with the in-repo SM83 assembler, verifies
every overwritten byte against the preimages in ``game_layout``, places
the generated tables and fixes the header.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from typing import Any

from . import game_layout as GL
from . import palettes as P
from . import rom_utils
from .sm83asm import assemble

DX_SIZE = 0x40000
RST28, RST30 = 0xEF, 0xF7

# Windows that assembled sections may occupy (file offsets, inclusive-exclusive).
FREE_WINDOWS = [(0x0003, 0x0038), (0x0061, 0x0100), (0x20000, 0x40000)]


class PatchError(Exception):
    pass


@dataclass
class Tables:
    objpal: bytes      # 128
    base_bg: bytes     # 64
    base_obj: bytes    # 64
    lut_title: bytes   # 256
    lut_game: bytes    # 256
    lut_logo: bytes    # 256
    metapal: bytes     # 128


def _index(names: list[str], name: str, what: str) -> int:
    if name not in names:
        raise PatchError(f"{what}: unknown palette {name!r} (have {names})")
    return names.index(name)


def build_tables(pal_data: dict[str, Any], bg_cat: dict[str, Any], obj_cat: dict[str, Any]) -> Tables:
    enc = P.encode(pal_data)
    bg_names = P.names(pal_data, "bg_palettes")
    obj_names = P.names(pal_data, "obj_palettes")

    metapal = bytearray([_index(bg_names, bg_cat.get("default_metatile_palette", bg_names[0]), "default")] * 128)
    seen: dict[int, str] = {}
    for name, ids in (bg_cat.get("metatile_palettes") or {}).items():
        idx = _index(bg_names, name, "metatile_palettes")
        for g in ids:
            if not 0 <= g < 128:
                raise PatchError(f"metatile graphic {g:#x} out of range")
            if g in seen:
                raise PatchError(f"metatile graphic {g:#x} in both {seen[g]} and {name}")
            seen[g] = name
            metapal[g] = idx

    ui = _index(bg_names, bg_cat.get("ui_palette", bg_names[0]), "ui_palette")
    lut_game = bytearray([ui] * 256)
    for tile, name in (bg_cat.get("ui_overrides") or {}).items():
        lut_game[int(tile)] = _index(bg_names, name, "ui_overrides")

    def title_lut(key: str) -> bytes:
        spec = (bg_cat.get("title_screens") or {}).get(key) or {}
        lut = bytearray([_index(bg_names, spec.get("default", bg_names[0]), key)] * 256)
        for rng in spec.get("ranges") or []:
            idx = _index(bg_names, rng["palette"], f"{key}.ranges")
            for t in range(rng["first"], rng["last"] + 1):
                lut[t] = idx
        return bytes(lut)

    lut_title, lut_logo = title_lut("castle"), title_lut("logo")

    objpal = bytearray([_index(obj_names, obj_cat.get("default", obj_names[1]), "obj default")] * 128)
    for name, ids in (obj_cat.get("ids") or {}).items():
        idx = _index(obj_names, name, "obj ids")
        for i in ids:
            if not 0 <= i < 128 or i & 1:
                raise PatchError(f"sprite id {i:#x} must be even and < $80")
            objpal[i] = objpal[i | 1] = idx
    player = _index(obj_names, obj_cat.get("player", obj_names[0]), "player")
    if player != 0:
        raise PatchError("the player palette must be OBJ palette 0 (PLAYER_PAL in dx.asm)")
    return Tables(bytes(objpal), enc["bg"], enc["obj"], lut_title, bytes(lut_game), lut_logo, bytes(metapal))


def _asm_source() -> str:
    return resources.files("ultima_rov_dx").joinpath("asm/dx.asm").read_text(encoding="utf-8")


def build(original: bytes, pal_data: dict[str, Any], bg_cat: dict[str, Any], obj_cat: dict[str, Any]) -> tuple[bytes, dict[str, int]]:
    if len(original) != GL.ROM_BANKS * 0x4000:
        raise PatchError(f"expected a {GL.ROM_BANKS * 16} KiB ROM, got {len(original)} bytes")
    if original[0x147] != GL.CARTRIDGE_TYPE:
        raise PatchError(f"cartridge type {original[0x147]:#04x} != MBC2+battery")
    rom = bytearray(original) + bytearray([0xFF] * (DX_SIZE - len(original)))
    touched = bytearray(DX_SIZE)

    def put(off: int, data: bytes, what: str) -> None:
        for i in range(len(data)):
            if touched[off + i]:
                raise PatchError(f"{what}: overlaps earlier patch at {off + i:#x}")
            touched[off + i] = 1
        rom[off:off + len(data)] = data

    # 1. hooks: verify preimages
    for hook in GL.HOOKS:
        got = bytes(original[hook.offset:hook.offset + len(hook.preimage)])
        if got != hook.preimage:
            raise PatchError(f"hook {hook.name} at {hook.offset:#x}: expected {hook.preimage.hex()} got {got.hex()}")

    # 2. assemble
    sections, syms = assemble([("dx.asm", _asm_source())])
    hook_ranges = [(h.offset, h.offset + len(h.preimage)) for h in GL.HOOKS]
    for sec in sections:
        if sec.rom_offset is None:
            continue
        lo, hi = sec.rom_offset, sec.rom_offset + len(sec.data)
        in_free = any(a <= lo and hi <= b for a, b in FREE_WINDOWS)
        in_hook = any(a <= lo and hi <= b for a, b in hook_ranges)
        if not (in_free or in_hook):
            raise PatchError(f"section {sec.name} [{lo:#x},{hi:#x}) is neither free space nor a verified hook")
        if in_free and lo < len(original) and any(b != 0xFF for b in original[lo:hi]):
            raise PatchError(f"section {sec.name} overwrites non-free bytes")
        put(lo, bytes(sec.data), sec.name)

    # layout limits
    if syms["Bank8CodeEnd"] > syms["W2_IMAGE_ROM"]:
        raise PatchError("bank 8 code overlaps the WRAM2 image")
    if syms["W2CodeEnd"] > syms["OBJPAL"]:
        raise PatchError(f"WRAM2 code too large (ends {syms['W2CodeEnd']:#x})")

    # 3. LCD-on sites
    for sites, rst in ((GL.GAME_LCD_ON_SITES, RST28), (GL.TITLE_LCD_ON_SITES, RST30)):
        for bank, addr in sites:
            off = GL.file_offset(bank, addr)
            pre = original[off - 2:off + 2]
            if not (pre[0] == 0x3E and pre[1] & 0x80 and pre[2:] == b"\xE0\x40"):
                raise PatchError(f"LCD-on site {bank}:{addr:04x}: unexpected bytes {bytes(pre).hex()}")
            put(off, bytes([rst, 0x00]), f"lcd_on {bank}:{addr:04x}")

    # 4. tables
    t = build_tables(pal_data, bg_cat, obj_cat)
    w2_rom = GL.file_offset(GL.DX_RUNTIME_BANK, syms["W2_IMAGE_ROM"])

    def w2(addr: int, data: bytes, what: str) -> None:
        put(w2_rom + (addr - syms["W2_BASE"]), data, what)

    w2(syms["OBJPAL"], t.objpal, "OBJPAL")
    w2(syms["BASE_BG"], t.base_bg, "BASE_BG")
    w2(syms["BASE_OBJ"], t.base_obj, "BASE_OBJ")
    w2(syms["LAST_BGP"], bytes([0xFF, 0xFF, 0xFF, 0xFF]), "vars")   # force first sync + LUT build
    w2(syms["SLOTPAL"], bytes([t.metapal[0]] * 16), "SLOTPAL")
    w2(syms["LUT_TITLE"], t.lut_title, "LUT_TITLE")
    w2(syms["LUT_GAME"], t.lut_game, "LUT_GAME")
    w2(syms["LUT_LOGO"], t.lut_logo, "LUT_LOGO")
    w2(syms["LUT"], t.lut_game, "LUT")
    put(GL.file_offset(GL.DX_RUNTIME_BANK, syms["METAPAL"]), t.metapal, "METAPAL")

    # 5. header
    rom[0x143] = 0x80                     # CGB enhanced, DMG compatible
    rom[0x148] = GL.DX_ROM_SIZE_CODE
    out = rom_utils.fix_global_checksum(rom_utils.fix_header_checksum(bytes(rom)))
    return out, syms
