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

from . import branding as BR
from . import game_layout as GL
from . import palettes as P
from . import rom_utils
from .sm83asm import assemble

DX_SIZE = 0x40000
RST28, RST30 = 0xEF, 0xF7
MAX_THEMES = 4    # dx.asm MAX_THEMES / BG_THEMES size

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
    metapal: bytes     # 128 per theme
    area_theme: bytes  # 256: theme index per area id ($D12F)
    bg_themes: bytes   # MAX_THEMES x 64: BG base colours per theme
    picture_lut: bytes = bytes(256)   # entrance cutscene tile -> palette
    entrance_theme: int = 0           # theme index of title cards + cutscene
    flat_bg: bytes = bytes(8)         # colours for blank/flat DMG palettes
    picture_fix: bytes = b"\0\0"      # entrance cutscene attribute fixups: (lo, hi, attr)*, 0, 0
    lut_menu: bytes = bytes(256)      # start menu tile -> palette (items overlaid at run time)
    item_pal: bytes = bytes(64)       # BG palette per item id (inventory + side-panel icons)
    ui_theme: int = 0                 # theme of text screens, dialogs and the start menu
    menu_obj: bytes = bytes(8)        # start-menu cursor colours (OBJ palette 7 in menu mode)
    fire_obj: bytes = bytes(8)        # wand fireball colours (OBJ palette 7 on map screens)
    ship_pal: int = 0                 # OBJ palette of the sailing ship (sprite in an unloaded slot)
    text_ranges: bytes = b"\0\0"   # text screens, then champion select: count, (first, last, pal)*


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

    def title_lut_from(spec: dict[str, Any], key: str) -> bytes:
        lut = bytearray([_index(bg_names, spec.get("default", bg_names[0]), key)] * 256)
        for rng in spec.get("ranges") or []:
            idx = _index(bg_names, rng["palette"], f"{key}.ranges")
            for t in range(rng["first"], rng["last"] + 1):
                lut[t] = idx
        return bytes(lut)

    def title_lut(key: str) -> bytes:
        return title_lut_from((bg_cat.get("title_screens") or {}).get(key) or {}, key)

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
    # area themes: theme 0 = base palettes/metatile map, then bg_tile_categories.area_themes in order
    metapals, bg_sets = [bytes(metapal)], [enc["bg"]]
    area_theme = bytearray(256)
    color_themes = pal_data.get("bg_themes") or {}
    for tname, spec in (bg_cat.get("area_themes") or {}).items():
        t = len(metapals)
        if t >= MAX_THEMES:
            raise PatchError(f"at most {MAX_THEMES - 1} area themes")
        mp = bytearray(metapal)
        seen_t: dict[int, str] = {}
        for name, ids in (spec.get("metatile_palettes") or {}).items():
            idx = _index(bg_names, name, f"area_themes.{tname}")
            for g in ids:
                if not 0 <= g < 128:
                    raise PatchError(f"metatile graphic {g:#x} out of range")
                if g in seen_t:
                    raise PatchError(f"area theme {tname}: graphic {g:#x} in both {seen_t[g]} and {name}")
                seen_t[g] = name
                mp[g] = idx
        metapals.append(bytes(mp))
        colors = color_themes.get(tname) or {}
        overrides = {k: v for k, v in colors.items()}
        for k in overrides:
            _index(bg_names, k, f"bg_themes.{tname}")
        merged = {n: overrides.get(n, pal_data["bg_palettes"][n]) for n in bg_names}
        bg_sets.append(P.encode({"bg_palettes": merged, "obj_palettes": pal_data["obj_palettes"]})["bg"])
        for area in spec.get("areas") or []:
            if not 0 <= area < 256:
                raise PatchError(f"area id {area:#x} out of range")
            if area_theme[area]:
                raise PatchError(f"area {area:#x} in two themes")
            area_theme[area] = t
    # every area the game draws from the dungeon atlas (not in surface_areas)
    # and not listed above gets dungeon_theme
    dungeon = bg_cat.get("dungeon_theme")
    if dungeon is not None:
        names_t = ["base"] + list((bg_cat.get("area_themes") or {}).keys())
        if dungeon not in names_t[1:]:
            raise PatchError(f"dungeon_theme {dungeon!r} is not an area_themes entry")
        surface = set(bg_cat.get("surface_areas") or [])
        if not surface:
            raise PatchError("dungeon_theme needs surface_areas")
        for area in range(256):
            if area not in surface and not area_theme[area]:
                area_theme[area] = names_t.index(dungeon)
    for name in color_themes:
        if name not in (bg_cat.get("area_themes") or {}):
            raise PatchError(f"bg_themes.{name} has no area_themes entry")
    bg_themes = b"".join(bg_sets) + bytes(64 * (MAX_THEMES - len(bg_sets)))
    theme_names = ["base"] + list((bg_cat.get("area_themes") or {}).keys())
    entrance = bg_cat.get("entrance_theme")
    entrance_theme = 0
    if entrance is not None:
        if entrance not in theme_names[1:]:
            raise PatchError(f"entrance_theme {entrance!r} is not an area_themes entry")
        entrance_theme = theme_names.index(entrance)
    pic_spec = (bg_cat.get("pictures") or {}).get("entrance") or {}
    picture_lut = bytes(title_lut_from(pic_spec, "pictures.entrance"))
    fix = bytearray()
    for f in pic_spec.get("fixups") or []:
        if not (0 <= f["row"] < 32 and 0 <= f["col"] < 32):
            raise PatchError(f"pictures.entrance fixup {f} outside the 32x32 map")
        addr = 0x9800 + 32 * f["row"] + f["col"]
        fix += bytes([addr & 0xFF, addr >> 8, _index(bg_names, f["palette"], "pictures.entrance.fixups")])
    fix += b"\0\0"
    if len(fix) > 256:
        raise PatchError("too many pictures.entrance fixups")
    flat = pal_data.get("flat_bg") or ["#FFFFFF", "#B0B0B0", "#606060", "#000000"]
    if len(flat) != 4:
        raise PatchError("flat_bg needs 4 colours")
    flat_bg = b"".join(P.bgr555(c).to_bytes(2, "little") for c in flat)
    ui_name = bg_cat.get("ui_theme")
    ui_theme = 0
    if ui_name is not None:
        if ui_name not in theme_names[1:]:
            raise PatchError(f"ui_theme {ui_name!r} is not an area_themes entry")
        ui_theme = theme_names.index(ui_name)
    lut_menu = title_lut_from(bg_cat.get("menu_screen") or {}, "menu_screen")
    item_pal = bytearray([ui] * 64)
    seen_i: dict[int, str] = {}
    for name, ids in (bg_cat.get("item_palettes") or {}).items():
        idx = _index(bg_names, name, "item_palettes")
        for i in ids:
            if not 0 <= i < 64:
                raise PatchError(f"item id {i:#x} out of range (0-$3F)")
            if i in seen_i:
                raise PatchError(f"item {i:#x} in both {seen_i[i]} and {name}")
            seen_i[i] = name
            item_pal[i] = idx
    text_ranges = bytearray()
    for key in ("text_screen", "champion_screen"):
        rngs = (bg_cat.get(key) or {}).get("ranges") or []
        text_ranges.append(len(rngs))
        for rng in rngs:
            if not 0 <= rng["first"] <= rng["last"] <= 0xFF:
                raise PatchError(f"{key}: bad tile range {rng}")
            text_ranges += bytes([rng["first"], rng["last"], _index(bg_names, rng["palette"], f"{key}.ranges")])
        cursor = pal_data.get("menu_cursor") or ["#FFFFFF", "#F8E080", "#F09838", "#D83020"]
    if len(cursor) != 4:
        raise PatchError("menu_cursor needs 4 colours")
    menu_obj = b"".join(P.bgr555(c).to_bytes(2, "little") for c in cursor)
    fire = pal_data.get("wand_fire") or cursor
    if len(fire) != 4:
        raise PatchError("wand_fire needs 4 colours")
    fire_obj = b"".join(P.bgr555(c).to_bytes(2, "little") for c in fire)
    ship_pal = _index(obj_names, obj_cat.get("ship", obj_cat.get("player", obj_names[0])), "ship")
    return Tables(bytes(objpal), enc["bg"], enc["obj"], lut_title, bytes(lut_game), lut_logo,
                  b"".join(metapals), bytes(area_theme), bg_themes, picture_lut, entrance_theme, flat_bg, bytes(fix),
                  lut_menu, bytes(item_pal), ui_theme, menu_obj, fire_obj, ship_pal, bytes(text_ranges))


def _asm_source() -> str:
    return resources.files("ultima_rov_dx").joinpath("asm/dx.asm").read_text(encoding="utf-8")


def build(original: bytes, pal_data: dict[str, Any], bg_cat: dict[str, Any], obj_cat: dict[str, Any],
          brand: dict[str, Any] | None = None) -> tuple[bytes, dict[str, int]]:
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
    if syms["MAX_THEMES"] != MAX_THEMES:
        raise PatchError("MAX_THEMES mismatch between dx.asm and dx_patch.py")
    if (syms["W2_IMAGE_ROM"] + syms["W2_IMAGE_LEN"] > syms["AREA_THEME"] or syms["AREA_THEME"] + 256 > syms["PICTURE_LUT"]
            or syms["PICTURE_LUT"] + 256 > syms["PICTURE_FIX"] or syms["PICTURE_FIX"] + 256 > syms["METAPAL"]
            or syms["METAPAL"] + 128 * MAX_THEMES > syms["LUT_TITLE_ROM"] or syms["LUT_TITLE_ROM"] + 256 > syms["LUT_LOGO_ROM"]
            or syms["LUT_LOGO_ROM"] + 256 > syms["BRAND_TILES"]
            or syms["BRAND_TILES"] + syms["BRAND_TILES_LEN"] > syms["BRAND_CELLS"] or syms["BRAND_CELLS"] + 256 > 0x8000):
        raise PatchError("bank 8 table layout overlap")
    if syms["W2bEnd"] > syms["FIRE_OBJ"] or syms["BG_THEMES"] + 64 * MAX_THEMES > syms["UnloadedPal"]:
        raise PatchError(f"WRAM2 section wram2b overlaps BG_THEMES or ends past $E000 ({syms['W2bEnd']:#x})")
    if syms["W2CodeEnd"] > syms["OBJPAL"]:
        raise PatchError(f"WRAM2 code too large (ends {syms['W2CodeEnd']:#x})")

    if syms["PICTURE_BANK"] != syms["TITLE_BANK"] or any(b != syms["TITLE_BANK"] for b, _ in GL.TITLE_LCD_ON_SITES):
        raise PatchError("title/picture LCD-on sites must all be in TITLE_BANK (LUTs are copied from bank 8)")
    if (syms["INV"] + 64 > syms["SLOTG"] or syms["ITEM_PAL"] + 64 > syms["INV"] or syms["HR_BACKUP"] + 12 > syms["TEXT_RANGES"]
            or syms["TEXT_RANGES"] + syms["TEXT_RANGES_LEN"] > syms["ITEM_PAL"]):
        raise PatchError("WRAM2 variable layout overlap")

    # 3. LCD-on sites
    unknown = GL.MAP_LCD_ON_SITES - set(GL.GAME_LCD_ON_SITES)
    if unknown:
        raise PatchError(f"MAP_LCD_ON_SITES not in GAME_LCD_ON_SITES: {sorted(unknown)}")
    for sites, rst in ((GL.GAME_LCD_ON_SITES, RST28), (GL.TITLE_LCD_ON_SITES, RST30)):
        for bank, addr in sites:
            # rst $28 is followed by a mode byte that is also a no-op opcode:
            # $00 nop = map screen, $40 ld b,b = text screen (see W2LcdOn)
            if rst == RST30 or (bank, addr) in GL.MAP_LCD_ON_SITES:
                mode = 0x00                  # nop: map screen
            elif (bank, addr) in GL.CARD_LCD_ON_SITES:
                mode = 0x49                  # ld c,c: title card
            elif (bank, addr) in GL.PICTURE_LCD_ON_SITES:
                if bank != syms["PICTURE_BANK"]:
                    raise PatchError("picture LCD-on sites must be in PICTURE_BANK")
                mode = 0x52                  # ld d,d: entrance cutscene
            elif (bank, addr) in GL.BLANK_LCD_ON_SITES:
                mode = 0x5B                  # ld e,e: blank screen
            elif (bank, addr) in GL.MENU_LCD_ON_SITES:
                mode = 0x64                  # ld h,h: start menu
            elif (bank, addr) in GL.DIALOG_LCD_ON_SITES:
                mode = 0x6D                  # ld l,l: dialog (text + side panel)
            elif (bank, addr) in GL.CHAMPION_LCD_ON_SITES:
                mode = 0x7F                  # ld a,a: champion select (text + portraits)
            else:
                mode = 0x40                  # ld b,b: text screen
            off = GL.file_offset(bank, addr)
            pre = original[off - 2:off + 2]
            if not (pre[0] == 0x3E and pre[1] & 0x80 and pre[2:] == b"\xE0\x40"):
                raise PatchError(f"LCD-on site {bank}:{addr:04x}: unexpected bytes {bytes(pre).hex()}")
            put(off, bytes([rst, mode]), f"lcd_on {bank}:{addr:04x}")

    # 4. tables
    t = build_tables(pal_data, bg_cat, obj_cat)
    w2_rom = GL.file_offset(GL.DX_RUNTIME_BANK, syms["W2_IMAGE_ROM"])

    def w2(addr: int, data: bytes, what: str) -> None:
        put(w2_rom + (addr - syms["W2_BASE"]), data, what)

    w2(syms["OBJPAL"], t.objpal, "OBJPAL")
    w2(syms["BASE_BG"], t.base_bg, "BASE_BG")
    w2(syms["BASE_OBJ"], t.base_obj, "BASE_OBJ")
    w2(syms["LAST_BGP"], bytes([0xFF, 0xFF, 0xFF, 0xFF, 0x00, t.entrance_theme, 0x00, 0x00]), "vars")   # force first sync + LUT build; CUR_THEME 0, MAP_THEME 0
    w2(syms["UI_THEME"], bytes([t.ui_theme, 0, 0]), "UI_THEME/LIVE")
    w2(syms["SHIP_PAL"], bytes([t.ship_pal, 0, 0]), "SHIP_PAL/SWEEP")
    w2(syms["MENU_OBJ"], t.menu_obj, "MENU_OBJ")
    w2(syms["FIRE_OBJ"], t.fire_obj, "FIRE_OBJ")
    if len(t.text_ranges) > syms["TEXT_RANGES_LEN"]:
        raise PatchError(f"text_screen + champion_screen ranges: {len(t.text_ranges)} bytes > {syms['TEXT_RANGES_LEN']}")
    w2(syms["TEXT_RANGES"], t.text_ranges, "TEXT_RANGES")
    w2(syms["ITEM_PAL"], t.item_pal, "ITEM_PAL")
    w2(syms["LUT_MENU"], t.lut_menu, "LUT_MENU")
    w2(syms["FLAT_BG"], t.flat_bg, "FLAT_BG")
    put(GL.file_offset(GL.DX_RUNTIME_BANK, syms["PICTURE_LUT"]), t.picture_lut, "PICTURE_LUT")
    put(GL.file_offset(GL.DX_RUNTIME_BANK, syms["PICTURE_FIX"]), t.picture_fix, "PICTURE_FIX")
    w2(syms["BG_THEMES"], t.bg_themes, "BG_THEMES")
    put(GL.file_offset(GL.DX_RUNTIME_BANK, syms["AREA_THEME"]), t.area_theme, "AREA_THEME")
    w2(syms["SLOTPAL"], bytes([t.metapal[0]] * 16), "SLOTPAL")
    put(GL.file_offset(GL.DX_RUNTIME_BANK, syms["LUT_TITLE_ROM"]), t.lut_title, "LUT_TITLE_ROM")
    w2(syms["LUT_GAME"], t.lut_game, "LUT_GAME")
    lut_logo = bytearray(t.lut_logo)
    brand_tiles, brand_cells = (b"", [])
    if brand:
        try:
            brand_tiles, brand_cells = BR.build(original, brand)
        except BR.BrandingError as e:
            raise PatchError(f"branding: {e}") from None
        if int(brand.get("first_tile", 0xA0)) != 0xA0:
            raise PatchError("branding first_tile must be $A0 (dx.asm BRAND_VRAM)")
        if len(brand_tiles) > syms["BRAND_TILES_LEN"]:
            raise PatchError("branding tiles exceed BRAND_TILES_LEN")
        bg_names = P.names(pal_data, "bg_palettes")
        set_by: dict[int, str] = {}
        for _row, _col, tile, pal in brand_cells:
            if set_by.setdefault(tile, pal) != pal:
                raise PatchError(f"branding tile {tile:#x} used with two palettes")
            lut_logo[tile] = _index(bg_names, pal, "branding")
    cells = bytearray()
    for row, col, tile, _pal in brand_cells:
        addr = 0x9800 + 32 * row + col
        cells += bytes([addr & 0xFF, addr >> 8, tile])
    cells += b"\0\0"
    put(GL.file_offset(GL.DX_RUNTIME_BANK, syms["BRAND_TILES"]),
        brand_tiles + bytes(syms["BRAND_TILES_LEN"] - len(brand_tiles)), "BRAND_TILES")
    put(GL.file_offset(GL.DX_RUNTIME_BANK, syms["BRAND_CELLS"]), bytes(cells), "BRAND_CELLS")
    put(GL.file_offset(GL.DX_RUNTIME_BANK, syms["LUT_LOGO_ROM"]), bytes(lut_logo), "LUT_LOGO_ROM")
    w2(syms["LUT"], t.lut_game, "LUT")
    put(GL.file_offset(GL.DX_RUNTIME_BANK, syms["METAPAL"]), t.metapal, "METAPAL")

    # 5. header
    rom[0x143] = 0x80                     # CGB enhanced, DMG compatible
    rom[0x148] = GL.DX_ROM_SIZE_CODE
    out = rom_utils.fix_global_checksum(rom_utils.fix_header_checksum(bytes(rom)))
    return out, syms
