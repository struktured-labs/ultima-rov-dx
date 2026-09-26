# Background tiles and maps

## Metatile slots
Gameplay BG uses 2x2 metatiles. 16 HRAM slots `$FFA0-$FFAF` each hold a graphic index g.
Slot s occupies tiles `s*4 .. s*4+3` at VRAM `$9000+s*64`.
Loader: bank1 `$4ECD-$4F7C`, which copies graphic bytes bank1 `$689B + g*64` via `call $01A9` at `$4F6C`
(**DX hook -> Far8Slot**). g = (DE - `$689B`) >> 6.

* g 0..63: atlas A (towns/castles/dungeons).
* g 64..: atlas B (overworld), selected through remap table bank1 `$7E74` when `[$D12F]` is in the list
  at `$7E8B` = `00 02 03 04 05 32 33 4E 51`.
* The overworld also uses atlas-A g `$0A` (plains) and `$0B` (water).

Identified graphics (see `palettes/bg_tile_categories.yaml`, `metatile_palettes`):
plains `$0A` grass, water `$0B`, castle floor `$50` stone, brick `$08` earth, trees, mountains,
towns/wood, ankh/shrine gold, lava/fire. Identification was done with `tmp/slotmap.py`
(per-screen-cell graphic dump) plus visual inspection.

## Tile program (scrolling / full redraw)
bank1 `$4A61` generates straight-line code at `$D800` using `31 lo hi` (ld sp,map), `01 lo hi`
(ld bc,tiles), `C5` (push bc), `D5` (push de). The terminator `jp $4B8F` is written at `$4B3C`
(**DX hook -> Far8Term**). `$4B45` waits for VBlank, `di; jp $D800`; the program returns to
`$4B8F`. Worst case about 924 M-cycles from LY 144, so a second (attribute) program only fits in
VBlank with CGB double speed.

## Other writers
* `$066B` single metatile writer (**DX hook -> MetaHook**, writes 4 attributes).
* Title / menus / status bar / dialog: drawn with the LCD off; LCD-on sites are listed in
  `game_layout.GAME_LCD_ON_SITES` / `TITLE_LCD_ON_SITES` (**DX hook: rst $28 / rst $30**, full
  attribute recompute while the LCD is still off).
* Logo dissolve bank7 `$4BD1` copies `$98xx -> $9Cxx` with the LCD on (**DX hook: rst $20**).
* Title castle: LCDC `$81`, tiles `$00-$C1` laid out in reading order. Logo: LCDC `$89` (map `$9C00`).
