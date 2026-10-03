"""Game-specific facts about Ultima: Runes of Virtue (USA).

Every value here was established by reverse engineering the verified ROM
(SHA-256 9008df8d...c993d7, see docs/rom_facts.md) with the mgbdis
disassembly, PyBoy runs and the scripts/probes/sm83.py tracer. Notes with
the evidence live in reverse_engineering/notes/ (memory_map.md,
bg_tiles.md, sprites.md, colorization_design.md).

Addresses are CPU addresses; ``file_offset(bank, addr)`` converts.
Nothing here was copied from penta-dragon-dx.
"""

from __future__ import annotations

from dataclasses import dataclass


def file_offset(bank: int, addr: int) -> int:
    return addr if addr < 0x4000 else bank * 0x4000 + (addr - 0x4000)


@dataclass(frozen=True)
class Hook:
    """A patch site whose original bytes must match ``preimage`` exactly."""

    name: str
    offset: int | None       # file offset in the original ROM
    preimage: bytes | None   # exact original bytes expected at offset
    note: str


# ---------------------------------------------------------------- cartridge
CARTRIDGE_TYPE = 0x06        # MBC2 + battery (header 0x147)
ROM_BANKS = 8                # 128 KiB original (header 0x148 = 0x02)
DX_ROM_SIZE_CODE = 0x03      # DX build: 256 KiB (MBC2 maximum), banks 8-15 free
DX_RUNTIME_BANK = 8          # bank holding the DX code and WRAM2 image
BANK_SELECT_SHADOW = None    # the game keeps NO shadow of the ROM bank (verified: writes $2100 directly)
MBC2_BANK_REGISTER = 0x2100  # any $0000-$3FFF address with bit 8 set; low 4 bits = bank

# ---------------------------------------------------------------- vectors / core
ENTRY_JP = 0x0150            # jp $1AE2 (also rst $00 target)
GAME_INIT = 0x1AE2           # di; SP=$CFFF; init; LCDC=$E7; main loop ~$1B7B
VBLANK_ISR = 0x1ACB          # push af; if [$C522]!=1: call $FF80; [$FF8E]=1
STAT_ISR = 0x1A9F            # link/serial byte pump ($CC00 page); no $Dxxx access
OAM_DMA_HRAM = 0xFF80        # di; DMA from $C000; ei; ret (source bank3:$735C, 12 bytes)
OAM_DMA_CALLERS = (0x03A8, 0x10D3, 0x1762, 0x1AD3, 0x1EF3, 0x2BE5, (1, 0x50C0), (1, 0x52C3), (1, 0x52F3))
SHADOW_OAM = 0xC000          # also used as a text buffer while $C522 == 1
VBLANK_FLAG = 0xFF8E
DMA_INHIBIT = 0xC522         # 1 = ISR must not DMA (tile program running / dialogs)
WAIT_LY91 = 0x02DC           # busy-wait LY == $91 (returns at once if LCD off)
COPY64 = 0x01A9              # wait LY $91, copy 64 bytes DE -> HL
MEMCPY = 0x01A0              # HL -> DE, BC bytes
LCD_OFF_ROUTINES = (0x078F, 0x079D)

# ---------------------------------------------------------------- BG pipeline
SHADOW_TILEMAP = 0xC100      # $C100-$C4FF mirrors $9800-$9BFF
TILE_PROGRAM = 0xD800        # generated code: 31 lo hi / 01 lo hi / C5 / D5 / C3 8F 4B
TILE_PROGRAM_GENERATOR = (1, 0x4A61)
TILE_PROGRAM_EXECUTOR = (1, 0x4B45)
TILE_PROGRAM_RETURN = (1, 0x4B8F)
METATILE_WRITER = 0x066B     # A=tile t, HL=map: [t,t+2 / t+1,t+3]; returns HL+$21, A=t+4
SLOT_IDS = 0xFFA0            # 16 HRAM bytes: metatile graphic per slot ($FF empty)
SLOT_LOADER = (1, 0x4ECD)    # copies graphic bank1:$689B+g*64 into $9000+s*64
METATILE_GFX_BASE = 0x689B   # bank 1; overworld set at $789B (= g 64..)
SPRITE_IDS = 0xC580          # 16 bytes: graphic id per sprite slot
SPRITE_LOADER = 0x28E1       # slot b -> tiles $80+b*8 (VRAM $8800+b*$80)
MONSTER_GFX = (6, 0x6AD9)    # sprite id bit 6 = 0
PEOPLE_GFX = (1, 0x5A92)     # sprite id bit 6 = 1

# ---------------------------------------------------------------- free space
# Bank 0: $0003-$0027, $0028-$0037 (rst vectors, unused by the game; $0038
# kept because rst $38 on $FF is the crash trap) and $0061-$00FF.
FREE_SPACE: tuple[tuple[int, int], ...] = (
    (0x0003, 0x0025),
    (0x0028, 0x0010),
    (0x0061, 0x009F),
    (0x20000, 0x20000),      # banks 8-15 after expansion to 256 KiB
)
FREE_HRAM = ((0xFF98, 8), (0xFFE8, 0x17))
# WRAM bank 2 ($D000-$DFFF with SVBK=2) is entirely unused by the DMG game.

# ---------------------------------------------------------------- hooks
HOOKS: tuple[Hook, ...] = (
    Hook("boot", 0x0150, bytes.fromhex("c3e21a"), "jp $1AE2 -> jp Boot (CGB init)"),
    Hook("hram_dma_routine", file_offset(3, 0x735C), bytes.fromhex("f33ec0e0463e283d20fdfbc9"),
         "12-byte OAM DMA routine copied to $FF80 by bank3:$7071 -> jp DmaHook + relocated core"),
    Hook("metatile_writer", 0x066B, bytes.fromhex("22c602"), "ld [hl+],a; add 2 -> jp MetaHook"),
    Hook("tile_program_terminator", file_offset(1, 0x4B3C), bytes.fromhex("3ec3223e8f223e4b77"),
         "writes jp $4B8F at end of $D800 program -> call Far8Term (translate)"),
    Hook("slot_copy", file_offset(1, 0x4F6C), bytes.fromhex("cda901"),
         "call $01A9 in the metatile slot loader -> call Far8Slot"),
    Hook("hud_icons", 0x04E6, bytes.fromhex("cda9013e01ea0021c9"),
         "tail of $04C1 (A/B item icons -> tiles $F8-$FF): call $01A9; ld a,1; ld [$2100],a; ret -> call $01A9; jp HudTramp"),
    Hook("logo_dissolve", file_offset(7, 0x4BD1), bytes.fromhex("7e12"),
         "title dissolve copies $98xx->$9Cxx with LCD on -> rst $20 (copies attribute too)"),
)
PALETTE_INIT_HOOK = HOOKS[0]
VBLANK_HOOK = HOOKS[1]   # OAM DMA is called from ~10 sites, so the hook is the HRAM routine itself
TILEMAP_WRITER_HOOKS = HOOKS[2:4]

# LCD-on sites: `ld a,$xx (bit 7 set); ldh [rLCDC],a`. The `ldh` (e0 40) is
# replaced by `rst $28; nop` (game screens) or `rst $30; nop` (title art).
# (bank, address of the e0 40 instruction)
GAME_LCD_ON_SITES: tuple[tuple[int, int], ...] = (
    (0, 0x03A3), (0, 0x0AEB), (0, 0x10A8), (0, 0x1323), (0, 0x14FF), (0, 0x1804),
    (0, 0x1B17), (0, 0x23E2),
    (1, 0x4126), (1, 0x54E9),
    (3, 0x6E93), (3, 0x6EE1), (3, 0x6F78), (3, 0x6FAC), (3, 0x71FF), (3, 0x720E),
    (3, 0x7517), (3, 0x7526), (3, 0x7665), (3, 0x7697), (3, 0x7779), (3, 0x7788),
    (3, 0x78F8), (3, 0x7954), (3, 0x79C7), (3, 0x79FE), (3, 0x7A23), (3, 0x7A93),
    (3, 0x7AA2),
    (7, 0x40BF), (7, 0x4319), (7, 0x438B), (7, 0x4517), (7, 0x457E), (7, 0x4589),
    (7, 0x4619), (7, 0x4692), (7, 0x4853), (7, 0x4A40), (7, 0x4AE3),
    (7, 0x4C32), (7, 0x4C78), (7, 0x4C8D),
)
# Game sites whose screen is the play field (map mode: tiles $00-$3F take
# the metatile-slot palettes). Every other game site is a text/picture screen
# (story, champion select, dialogs, game over) where all tiles use the UI
# palette. Verified with tmp/sitetrace.py-style PyBoy hooks on rst $28:
# $03A3 restores the map after dialogs/menus, $1B17 overworld, $23E2 area
# entry, $10A8 start menu (mini-map); 1:$4126 (two-player start, serial
# link) and 1:$54E9 are map redraw paths (static reading, not seen firing).
MAP_LCD_ON_SITES: frozenset[tuple[int, int]] = frozenset({
    (0, 0x03A3), (0, 0x1B17), (0, 0x23E2),
    (1, 0x4126), (1, 0x54E9),
})
# Start menu (START during play; bank 0 $0FDB-$10A8, notes/menu.md): item grid
# (inventory $D100-$D11F drawn as 16x16 icons from bank 3 $4B00 + id*64 into
# tiles $0C-$8B), stats box with portrait, side panel in BG columns 22-23.
MENU_LCD_ON_SITES: frozenset[tuple[int, int]] = frozenset({(0, 0x10A8)})
# In-play dialog box screen (e.g. Lord British): text + side panel. Also
# $0AEB "You have reclaimed the rune of ..." after the rune cutscene and
# $14FF (two-player) "Please wait for the <champion> who has fallen!"
# (reverse_engineering/notes/ending.md); both were wrongly in map mode.
DIALOG_LCD_ON_SITES: frozenset[tuple[int, int]] = frozenset({(0, 0x1323), (0, 0x0AEB), (0, 0x14FF)})
# Champion select (bank 3; scripts/capture_screens.py CHARACTER_SELECT_LCD_ON
# and the tile-map dump in tmp/probe/textscreens.py): text screen whose four
# portraits use tiles $10-$1F, $20-$2F, $30-$3F and $80-$8F (4x4 each).
CHAMPION_LCD_ON_SITES: frozenset[tuple[int, int]] = frozenset({(3, 0x78F8), (3, 0x7954), (3, 0x79C7)})
# Dungeon entrance sequence (bank 7, reverse_engineering/notes/cutscene.md):
# $4619 title card ("The Cavern of Hatred"), $4692 the entrance cutscene
# (cliff, cave mouth, the champion walking in; LCDC $87, art from bank 7
# $5D50/$6550, map $6B90), $438B blank screen before the area is shown.
CARD_LCD_ON_SITES: frozenset[tuple[int, int]] = frozenset({(7, 0x4619)})
PICTURE_LCD_ON_SITES: frozenset[tuple[int, int]] = frozenset({(7, 0x4692)})
BLANK_LCD_ON_SITES: frozenset[tuple[int, int]] = frozenset({(7, 0x438B)})
TITLE_LCD_ON_SITES: tuple[tuple[int, int], ...] = (
    (7, 0x44F2),             # castle picture, LCDC $81 (tiles $00-$C1 in reading order)
    (7, 0x4BC2),             # "Ultima / Runes of Virtue" logo, LCDC $89 (map $9C00)
)

# Scene variables (partially understood; see memory_map.md, dungeons.md)
SCENE_STATE_ADDR = 0xD12F    # map/area id used by the slot loader's overworld remap
OVERWORLD_FLAG = 0xC511
AREA_MAP = 0xC600            # 16x16 cells of the current area, row-major; low 6 bits = graphic g
PLAYER_CELL = 0xFF91         # player cell index in AREA_MAP: high nibble row, low nibble column
FLOOR_ITEM_TILES = (0x40, 0x4F)   # BG tiles of floor pickups (hearts...) on map screens
AREA_IDS = {
    0x00: "Lord British's castle (throne room)",
    0x02: "overworld (Britannia, around the castle)",
    0x18: "Cavern of Hatred, entrance level (cave mouth due north of the castle)",
    0x19: "Cavern of Hatred, level 2 (down-ladder at $18 cell $9E)",
    0x1A: "Cavern of Hatred, level 3 (south-east exit of $19, cell $FD)",
}
# Area graphics list: the 16 metatile graphics of area $18 are stored at
# bank 4 $4CC8 (file 0x10CC8) with flag bits in bits 6-7, inside what looks
# like a per-area header (dims?, 16 graphics, compressed map). Not decoded yet.


def missing_facts() -> list[str]:
    """Names of facts the production builder needs but that are still unknown."""

    missing = []
    if CARTRIDGE_TYPE is None:
        missing.append("CARTRIDGE_TYPE")
    if PALETTE_INIT_HOOK.offset is None or PALETTE_INIT_HOOK.preimage is None:
        missing.append("PALETTE_INIT_HOOK")
    if not FREE_SPACE:
        missing.append("FREE_SPACE")
    return missing


# Side-panel digits 0-9 (tiles $E8-$F1; the gold count). Their font sits at
# bank 3 $4A00 as solid colour-3 glyphs; the DX redraws them in gold into VRAM
# bank 1 on map screens (dx_patch.gold_digits, bg_tile_categories panel_digits).
DIGIT_TILES = tuple(range(0xE8, 0xF2))
DIGIT_FONT = (3, 0x4A00)
# Title card (bank 7 $4602): HRAM byte holding the dungeon number shown
# (1 Hatred, 2 Deceit, 3 Cowardice, 4 Injustice, 5 Dishonor, 6 Selfishness,
# 7 Pride, 9 the Great Stygian Abyss).
CARD_NUMBER_HRAM = 0xFF8F
