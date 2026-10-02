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
MAX_THEMES = 4    # dx.asm MAX_THEMES: WRAM theme slots (BG_THEMES / THEME_OBJ)
ROM_THEMES = 32   # dx.asm ROM_THEMES: themes stored in bank 8
MP_SETS = 16      # dx.asm MP_SETS: distinct metatile palette maps (METAPAL), shared via MP_IDX
SLOT_SURFACE, SLOT_MAP, SLOT_ENTRANCE, SLOT_UI = 0, 1, 2, 3   # WRAM slots (dx.asm SLOT_MAP = 1)

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
    metapal: bytes     # 128 per metatile palette set (MP_SETS)
    area_theme: bytes  # 512: ROM theme per area id ($D12F), $D13E = 0 then $D13E = 1
    bg_themes: bytes   # MAX_THEMES x 64: BG base colours per WRAM slot
    picture_lut: bytes = bytes(256)   # entrance cutscene tile -> palette
    entrance_theme: int = 0           # theme index of title cards + cutscene
    flat_bg: bytes = bytes(8)         # colours for blank/flat DMG palettes
    picture_fix: bytes = b"\0\0"      # entrance cutscene attribute fixups: (lo, hi, attr)*, 0, 0
    lut_menu: bytes = bytes(256)      # start menu tile -> palette (items overlaid at run time)
    item_pal: bytes = bytes(64)       # BG palette per item id (inventory + side-panel icons)
    ui_theme: int = 0                 # theme of text screens, dialogs and the start menu
    menu_obj: bytes = bytes(8)        # start-menu cursor colours (OBJ palette 7 in menu mode)
    theme_obj: bytes = bytes(32)      # per WRAM slot: 4 colours of OBJ palette THEME_OBJ_SLOT
    fire_obj: bytes = bytes(8)        # wand fireball colours (OBJ palette 7 on map screens)
    ship_pal: int = 0                 # OBJ palette of the sailing ship (sprite in an unloaded slot)
    text_ranges: bytes = b"\0\0"   # text screens, then champion select: count, (first, last, pal)*
    theme_bg_rom: bytes = bytes(64 * ROM_THEMES)   # BG base colours per ROM theme (bank 8)
    theme_obj_rom: bytes = bytes(8 * ROM_THEMES)   # OBJ palette 5 per ROM theme (bank 8)
    rt_slot: bytes = bytes(ROM_THEMES)             # WRAM slot per ROM theme
    theme_names: tuple = ()                        # ROM theme names, index = theme
    first_map: int = 0                             # ROM theme initially in WRAM slot SLOT_MAP
    mp_idx: bytes = bytes(ROM_THEMES)              # METAPAL set per ROM theme


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
    area_theme = bytearray(512)      # [flag * 256 + area], flag = $D13E (second area set)
    color_themes = pal_data.get("bg_themes") or {}
    surface_claimed: set[int] = set()   # surface-atlas areas given a theme marked `surface: true`
    for tname, spec in (bg_cat.get("area_themes") or {}).items():
        t = len(metapals)
        if t >= ROM_THEMES:
            raise PatchError(f"at most {ROM_THEMES - 1} area themes")
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
        for key, half in (("areas", 0), ("areas_alt", 256)):
            for area in spec.get(key) or []:
                if not 0 <= area < 256:
                    raise PatchError(f"area id {area:#x} out of range")
                if area_theme[half + area]:
                    raise PatchError(f"area {area:#x} ({key}) in two themes")
                area_theme[half + area] = t
                if spec.get("surface"):
                    surface_claimed.add(half + area)
    # every area the game draws from the dungeon atlas (not in surface_areas)
    # and not listed above gets dungeon_theme
    dungeon = bg_cat.get("dungeon_theme")
    if dungeon is not None:
        names_t = ["base"] + list((bg_cat.get("area_themes") or {}).keys())
        if dungeon not in names_t[1:]:
            raise PatchError(f"dungeon_theme {dungeon!r} is not an area_themes entry")
        surface = set(bg_cat.get("surface_areas") or [])
        surface_alt = set(bg_cat.get("surface_areas_alt") or [])
        if not surface:
            raise PatchError("dungeon_theme needs surface_areas")
        for half, surf in ((0, surface), (256, surface_alt)):
            for area in range(256):
                if area not in surf and not area_theme[half + area]:
                    area_theme[half + area] = names_t.index(dungeon)
    for half, key in ((0, "surface_areas"), (256, "surface_areas_alt")):
        for area in bg_cat.get(key) or []:
            if area_theme[half + area] and half + area not in surface_claimed:
                raise PatchError(f"{key}: area {area:#x} is also in an area theme (mark the theme `surface: true`)")
    for i in surface_claimed:
        surf = set(bg_cat.get("surface_areas_alt" if i >= 256 else "surface_areas") or [])
        if i % 256 not in surf:
            raise PatchError(f"area {i % 256:#x}: `surface: true` themes may only list surface_areas")
    for name in color_themes:
        if name not in (bg_cat.get("area_themes") or {}):
            raise PatchError(f"bg_themes.{name} has no area_themes entry")
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
    slot_name = obj_names[5]
    ot = pal_data.get("obj_themes") or {}
    for tname in ot:
        if tname not in theme_names[1:]:
            raise PatchError(f"obj_themes.{tname} is not an area_themes entry")
        for pname in ot[tname]:
            if pname != slot_name:
                raise PatchError(f"obj_themes.{tname}.{pname}: only {slot_name!r} (OBJ palette 5) can follow the theme")
    obj_sets = []
    for tname in theme_names:
        spec = (ot.get(tname) or {}).get(slot_name) or pal_data["obj_palettes"][slot_name]
        obj_sets.append(b"".join(P.bgr555(c).to_bytes(2, "little") for c in spec["colors"]))
    # WRAM slots: 0 surface (theme 0), 1 the current dungeon (cache filled by
    # bank-8 MapTheme; starts with the first map theme), 2 entrance, 3 UI.
    if entrance_theme and entrance_theme == ui_theme:
        raise PatchError("entrance_theme and ui_theme must differ")
    rt_slot = bytearray([SLOT_MAP] * ROM_THEMES)
    rt_slot[0] = SLOT_SURFACE
    if entrance_theme:
        rt_slot[entrance_theme] = SLOT_ENTRANCE
    if ui_theme:
        rt_slot[ui_theme] = SLOT_UI
    for t in (entrance_theme, ui_theme):
        if t and t in area_theme:
            raise PatchError(f"theme {theme_names[t]!r} (entrance/UI) cannot be an area theme")
    first_map = next((t for t in range(1, len(theme_names)) if rt_slot[t] == SLOT_MAP), 0)
    slot_theme = [0, first_map, entrance_theme, ui_theme]
    bg_themes = b"".join(bg_sets[t] for t in slot_theme)
    theme_obj = bytearray(b"".join(obj_sets[t] for t in slot_theme))
    pad = ROM_THEMES - len(theme_names)
    theme_bg_rom = b"".join(bg_sets) + bytes(64 * pad)
    theme_obj_rom = b"".join(obj_sets) + bytes(8 * pad)
    sets: list[bytes] = []
    mp_idx = bytearray(ROM_THEMES)
    for t, mp in enumerate(metapals):
        if mp not in sets:
            sets.append(mp)
        mp_idx[t] = sets.index(mp)
    if len(sets) > MP_SETS:
        raise PatchError(f"at most {MP_SETS} distinct metatile palette maps (have {len(sets)})")
    metapals = sets + [bytes(128)] * (MP_SETS - len(sets))
    ship_pal = _index(obj_names, obj_cat.get("ship", obj_cat.get("player", obj_names[0])), "ship")
    return Tables(bytes(objpal), enc["bg"], enc["obj"], lut_title, bytes(lut_game), lut_logo,
                  b"".join(metapals), bytes(area_theme), bg_themes, picture_lut, SLOT_ENTRANCE if entrance_theme else 0,
                  flat_bg, bytes(fix),
                  lut_menu, bytes(item_pal), SLOT_UI if ui_theme else 0, menu_obj, bytes(theme_obj), fire_obj, ship_pal,
                  bytes(text_ranges), theme_bg_rom, theme_obj_rom, bytes(rt_slot), tuple(theme_names), first_map,
                  bytes(mp_idx))


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
    if syms["ROM_THEMES"] != ROM_THEMES or syms["SLOT_MAP"] != SLOT_MAP or syms["MP_SETS"] != MP_SETS:
        raise PatchError("ROM_THEMES / SLOT_MAP mismatch between dx.asm and dx_patch.py")
    if (syms["AREA_THEME"] & 0xFF or syms["METAPAL"] & 0xFF or syms["THEME_BG_ROM"] & 0xFF
            or (syms["THEME_OBJ_ROM"] & 0xFF) + 8 * ROM_THEMES > 0x100 or (syms["RT_SLOT"] & 0xFF) + ROM_THEMES > 0x100
            or (syms["MP_IDX"] & 0xFF) + ROM_THEMES > 0x100 or syms["METAPAL"] & 0x7F):
        raise PatchError("bank 8 theme tables must be page aligned (MapTheme / Slot index them by low byte)")
    if (syms["W2_IMAGE_ROM"] + syms["W2_IMAGE_LEN"] > syms["PICTURE_LUT"]
            or syms["PICTURE_LUT"] + 256 > syms["PICTURE_FIX"] or syms["PICTURE_FIX"] + 256 > syms["LUT_TITLE_ROM"]
            or syms["LUT_TITLE_ROM"] + 256 > syms["LUT_LOGO_ROM"]
            or syms["LUT_LOGO_ROM"] + 256 > syms["BRAND_TILES"]
            or syms["BRAND_TILES"] + syms["BRAND_TILES_LEN"] > syms["BRAND_CELLS"] or syms["BRAND_CELLS"] + 256 > syms["AREA_THEME"]
            or syms["AREA_THEME"] + 512 > syms["METAPAL"] or syms["METAPAL"] + 128 * MP_SETS > syms["THEME_BG_ROM"]
            or syms["THEME_BG_ROM"] + 64 * ROM_THEMES > syms["THEME_OBJ_ROM"]
            or syms["THEME_OBJ_ROM"] + 8 * ROM_THEMES > syms["RT_SLOT"] or syms["RT_SLOT"] + ROM_THEMES > syms["MP_IDX"] or syms["MP_IDX"] + ROM_THEMES > 0x8000):
        raise PatchError("bank 8 table layout overlap")
    if syms["W2bEnd"] > syms["THEME_OBJ"] or syms["BG_THEMES"] + 64 * MAX_THEMES > syms["UnloadedPal"]:
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
    w2(syms["SHIP_PAL"], bytes([t.ship_pal, 0, 0, t.first_map]), "SHIP_PAL/SWEEP/MAP_CACHED")
    w2(syms["MENU_OBJ"], t.menu_obj, "MENU_OBJ")
    w2(syms["FIRE_OBJ"], t.fire_obj, "FIRE_OBJ")
    if syms["THEME_OBJ_SLOT"] != 5 or syms["THEME_OBJ"] + len(t.theme_obj) > syms["FIRE_OBJ"]:
        raise PatchError("THEME_OBJ layout")
    w2(syms["THEME_OBJ"], t.theme_obj, "THEME_OBJ")
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
    put(GL.file_offset(GL.DX_RUNTIME_BANK, syms["THEME_BG_ROM"]), t.theme_bg_rom, "THEME_BG_ROM")
    put(GL.file_offset(GL.DX_RUNTIME_BANK, syms["THEME_OBJ_ROM"]), t.theme_obj_rom, "THEME_OBJ_ROM")
    put(GL.file_offset(GL.DX_RUNTIME_BANK, syms["RT_SLOT"]), t.rt_slot, "RT_SLOT")
    put(GL.file_offset(GL.DX_RUNTIME_BANK, syms["MP_IDX"]), t.mp_idx, "MP_IDX")
    w2(syms["SLOTPAL"], bytes([t.metapal[0]] * 16), "SLOTPAL")
    put(GL.file_offset(GL.DX_RUNTIME_BANK, syms["LUT_TITLE_ROM"]), t.lut_title, "LUT_TITLE_ROM")
    w2(syms["LUT_GAME"], t.lut_game, "LUT_GAME")
    lut_logo = bytearray(t.lut_logo)
    brand_tiles, brand_cells = (b"", [])
    if brand:
        try:
            brand_tiles, brand_cells = BR.build(brand)
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
