# Colorization design (DX runtime)

Source: `src/ultima_rov_dx/asm/dx.asm` assembled by `src/ultima_rov_dx/sm83asm.py`;
tables and patching in `src/ultima_rov_dx/dx_patch.py`; build with `uv run python scripts/build_dx.py`.

## Layout
* Header: `0x143=$80` (CGB-compatible, still runs on DMG), `0x148=$03` (256 KiB), checksums fixed.
* Bank 0 `$0003-$001F`: `Far8Term`, `Far8SlotInner`, `Far8` (call bank 8 `$4000` dispatcher, restore bank 1).
  `rst $20` DissolveCopy, `rst $28` LcdOnGame, `rst $30` LcdOnTitle. `$0061-$00FB`: AttrRun, DmaHook,
  LcdOn*, MetaHook, Far8Slot, DissolveCopy, AttrDone, Boot.
* Bank 8: dispatcher, `Term` (tile-program translator), `Slot`, `Bank8Boot`, the WRAM2 image
  (`$4400`, copied to `$D000-$DEFF`) and `METAPAL` (`$5800`, graphic g -> BG palette).
* WRAM bank 2: code `$D000`, `OBJPAL $D500` (sprite id -> OBJ palette), `BASE_BG $D580`,
  `BASE_OBJ $D5C0` (RGB555 base colors), live `LUT $D600` (tile -> attribute), vars `$D700`,
  `SLOTPAL $D7F0`, attribute program `$D800`, `LUT_MENU $DC00`, `LUT_GAME $DD00`, `BG_THEMES $DE00`
  (title/logo LUTs live in bank 8 `$5C00/$5D00` and are copied into `LUT` at LCD-on).
* HRAM `$FF98-$FF9B`: dispatch scratch, LCD mode, slot scratch, CGB flag.

## Flow
1. **Boot** (`$0150`): on CGB (A=`$11` and WRAM banking works) switch to double speed, copy
   the WRAM2 image, set `HR_CGB`; then `jp $1AE2`. On DMG every hook falls through to the original code.
2. **Tile program**: at the terminator the translator emits a matching attribute program in WRAM2
   `$D800` (same `ld sp` targets, fill registers translated through the LUT). The original program
   now ends with `jp AttrRun`, which sets VBK=1/SVBK=2, runs it, and `AttrDone` restores and jumps `$4B8F`.
3. **Slot loads** record `METAPAL[g]` for the slot's 4 tiles in the LUT.
4. **MetaHook** writes the 4 attributes of a single metatile.
5. **LCD-on**: mode switch (title castle / logo / game) swaps LUTs; all of `$9800-$9FFF` attributes
   are recomputed from the tile map while the LCD is still off.
6. **After each OAM DMA** (`DmaHook`): if BGP/OBP0/OBP1 changed, rebuild CRAM by mapping each DMG
   shade to the base colors (so fades to white/black work); then patch OAM attribute bits 0-2 in `$FE00`:
   player tiles (<`$80`) -> palette 0, monster/people tiles -> `OBJPAL[id]`, DMG-OBP1 sprites -> palette 7.

## Area themes (run 3)
* Theme = BG base colours (64 bytes, WRAM2 `BG_THEMES $DF00`, 4 slots) + metatile->palette map
  (bank 8 `METAPAL + theme*$80`). `AREA_THEME` (bank 8 `$5400`, 256 bytes) maps `[$D12F]` to a theme.
* `Slot` looks the theme up on every slot load; `SetTheme` copies the colours into `BASE_BG`
  and invalidates `LAST_BGP`, so CRAM is rewritten at the next OAM DMA (VBlank). Title screens
  (LCD modes 1/9) force theme 0.
* Theme `cavern` (areas `$18-$1A`): every non-UI palette shares a dusty floor colour 0 so furniture,
  doors, arrows and pickups sit on the floor; slate cobbles; pebbles `$23` use `earth`.

## Map vs text screens (run 3)
Game LCD-on sites are patched `rst $28` + a mode byte that is itself a harmless opcode:
`$00` (nop) = map screen (LUT from slot palettes + `LUT_GAME`), `$40` (`ld b,b`) = text screen
(every tile gets the UI palette). `W2LcdOn` reads the byte through the return address of the
`rst`. Map sites are listed in `game_layout.MAP_LCD_ON_SITES`; all other game sites are text.
This keeps dialog/story/champion/game-over screens clean while floor-item tiles `$40-$4F`
use `fire` (red hearts) on the map.

More mode bytes (dungeon entrance, see cutscene.md): `$49` (`ld c,c`) title card = text LUT +
`ENTRANCE_THEME`; `$52` (`ld d,d`) picture = LCD mode 3, LUT copied from bank 8 `PICTURE_LUT $5600`
(then bank 7 is mapped back: `PICTURE_BANK`), then per-cell attribute fixups from bank 8
`PICTURE_FIX $5700` (`lo, hi, attr` triples, `hi = 0` ends); `$5B` (`ld e,e`) blank = text + theme 0
with BG palette 0 colour 0 = `FLAT_BG[0]`.

## Start menu, dialogs and side panel (run 5)
Mode bytes `$64` (`ld h,h`, 0:`$10A8` start menu, LCD mode 4) and `$6D` (`ld l,l`, 0:`$1323`
dialog, mode 5). Text screens, dialogs and the menu use `UI_THEME` (`bg_themes.menu`); map
LCD-on restores `MAP_THEME`. Item icons get `ITEM_PAL[id]`, the side panel gets its glyph
palettes from `LUT_GAME`/`LUT_MENU`, and a hook at the end of `$04C1` plus a rotating refresh
after each OAM DMA keep the A/B icons and swapped slots coloured. Details: menu.md.
Bank-0 space was freed by moving the BC/DE/HL saves of DmaHook/LcdOnGame/MetaHook into
WRAM2 wrappers (`W2AfterDma`, `W2LcdOn`, `W2MetaW`).

## Flat DMG palettes
`SyncGroup` treats a DMG palette whose four shades are equal (`$00/$55/$AA/$FF`) as flat: all CGB
palettes of that group get `FLAT_BG[shade]` (`$D708`, 4 colours from `rov_palettes.yaml flat_bg`).
Blank transition frames are therefore uniform white instead of a mosaic of palette colour 0.

## Palettes
`palettes/rov_palettes.yaml`: BG ui, grass, water, stone, wood, earth, fire, gold; OBJ avatar, monster,
monster_strong, monster_elite (variant tiers, monsters.md), folk, royal, item, obp1. `bg_tile_categories.yaml` maps graphic g -> BG palette and title
tile ranges; `obj_categories.yaml` maps sprite id -> OBJ palette.

## Timing
Double speed keeps original game speed (the game is VBlank-paced; measured overworld scroll ≈1.1 px/frame
in both OG and DX) while giving the attribute program room inside VBlank.
