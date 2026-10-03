# Start menu and side panel (HUD)

## Start menu (START during play)
Built by bank 0 `$0FDB-$10A8`, switched on at 0:`$10A8` (`ld a,$8F; ldh [rLCDC],a`):
BG map `$9C00`, tiles `$8800` (signed), window off, `SCX=32` (the screen starts at map column 4).
DX mode byte `$64` (`ld h,h`) = LCD mode 4 (`game_layout.MENU_LCD_ON_SITES`).

Screen anatomy (tile ids):
* Item box (rows 0-6): 32 inventory slots in 4 rows of 8, each a 16x16 icon. Inventory is 32
  bytes at `$D100-$D11F` (`$FF` = empty). Slot c's icon is copied by `$2CFA` from bank 3
  `$4B00 + id*64` into canvas tiles `4*(c+3)`..+3 (`$0C-$8B`) and drawn with `$066B` at
  `$9C25 + (c&7)*2 + (c&$18)*8`.
* Stats box: champion portrait `$D4-$E3`, "AR" armour icon (`[$D134]`, tiles `$BC-$BF` at
  `$9D6B`), ST/IQ/DX (`$D121-$D123`) and score in digits `$E8-$F1`.
* Bottom box: messages, drawn with sprites.
* Frames: tiles `$02-$0B`.
* Side panel: BG columns 22-23 (screen columns 18-19), same layout as on the map (below).
* Cursor: OAM sprites 0/1 (tiles `$00`/`$02`, 8x16, graphic from bank 1 `$4E00`), index `$FF8F` (0-31).

Menu loop `$10AB`: OAM DMA only when the cursor moves (`$10D0`); `$C522 = 1` in the menu so the
VBlank ISR does no DMA. A/B on a slot swaps it with the A/B item (`$D126`/`$D125`) and calls
`$04C1` (panel icons) and `$01A9`; `$1140-$11B1` drops an item onto the map; potions/food (`$22`,
`$23`, `$2F`, `$36`) are used up from here. There is no separate stats/save/shop screen
reachable from the menu; 0:`$14FF` (LCDC `$8F`, text from bank 1 `$7F98`) is another text screen
(unobserved) handled as plain text.

## Item ids (`$00-$3F`, icon atlas bank 3 `$4B00`)
00 armour, 01 bow, 02 crossbow, 03 arrow, 04 shuriken, 05 boomerang, 06 flask, 07 staff, 08 dagger,
09 coin, 0A/0B armour, 0C rounded frame, 0D burst, 0E rock, 0F pick, 10 heart, 11 whip, 12 chain,
14 star, 17 lamp, 18 caltrops, 19-1B swords, 1D-1F keys, 20 armour, 21 chest, 22 food bowl,
23 red potion, 24-2B runes (hand, heart, sword, scales, flame, chalice, ankh, ?), 2C/2D rope,
2E boots, 2F food, 30 net, 31 ring, 32 chalice, 33 hammer, 36 ankh, 37 pipes, 38 compass,
3D green potion, 3E star, 3F burst. The palette of each is `item_palettes` in
`palettes/bg_tile_categories.yaml`.

## Side panel
Gameplay: the window (LCDC `$E7`, window map `$9C00`, `WX=151`), columns 0-1, so it does not
scroll with the map. Menu and dialogs: BG `$9C00` column `SCX/8 + 18`.

| row | tiles | content |
|-----|-------|---------|
| 0 | `$F2 $F6` | "A:" |
| 1-2 | `$F8 $FA / $F9 $FB` | A item icon (`$8F80` <- `[$D126]`) |
| 3 | `$F3 $F6` | "B:" |
| 4-5 | `$FC $FE / $FD $FF` | B item icon (`$8FC0` <- `[$D125]`) |
| 6 | `$F5 $F7` | gold coin |
| 7 | `$E8-$F1` | gold amount (shade 3 only) |
| 13-17 | col 0 `$F4`/`$E5`, col 1 `$E4`/`$E7` | hearts (full/empty), stars (full/empty) |

`$E6` is blank. `$04C1` copies both icons (via `$04D5`) and ends at `$04E6`
(`call $01A9; ld a,1; ld [$2100],a; ret`); callers: 0:`$0D06 $11FE $17EC $19DF $1AFA $2A08 $2D9D
$3DB8 $3FD9`, 1:`$4336 $5121`. None uses HL/DE/A after the return.

## DX implementation
* LCD mode 4 (menu): `LUT_MENU` (WRAM2 `$DC00`, from `menu_screen`) + `ITEM_PAL[id]` for the 4
  tiles of every slot, the armour icon and the A/B icons; theme `UI_THEME` (`bg_themes.menu`:
  every palette shares one paper colour 0, so coloured icons have no boxes). Cursor sprites
  (tiles < 4) use OBJ palette 7 = `MENU_OBJ` (`menu_cursor`, red/orange).
  The champion portrait (BG palette 5 = `PORTRAIT_PAL`, the `earth` slot, which no item uses)
  gets the current champion's `HERO_BG` colours: `SetThemeM` → bank-8 `HeroMenu8` on the menu
  LCD-on (`LCD_BYTE` `$64`); it sets `CUR_THEME` = `$FF` so the next screen reloads its theme.
* Mode 5 (dialog, 0:`$1323`): text LUT + `LUT_MENU[$E4-$FF]` + A/B icons, theme `UI_THEME`.
* Map (mode 0): `LUT_GAME` gives the panel glyphs their palettes (hearts use palette 0 whose
  shade 2 is red; stars/coin/"A:"/"B:" gold); icon tiles `$F8-$FF` follow `ITEM_PAL`, through
  `IconPal`: if that palette's colour 0 differs from the panel's (palette 0) on this screen,
  e.g. water/grass items on the overworld, the icon uses palette 0 instead, so it never sits on
  a tinted square. Surface themes (`overworld`, Lycaeum grounds, market, Simon's shop) give
  stone/wood/earth/fire the panel's colour 0.
* Live refresh: the icon tiles change without an LCD-on, so
  - `$04E6` is patched to `call $01A9; jp HudTramp`; HudTramp (bank 0) restores bank 1, then on CGB
    calls `W2Hud` (WRAM2) with D/E = A/B items. W2Hud (only in VBlank or LCD off, modes 0/4/5)
    recolours panel rows 1-5 and, in the menu, the slot under the cursor (just swapped); it returns
    through `HudExit` (`$0035`).
  - After every OAM DMA (`W2AfterDma`) 4 panel cells and, in the menu, 2 inventory slots are
    refreshed in rotation (`LIVE_R`, `LIVE_K`).
  - WRAM1 is read from WRAM2 code by a 12-byte helper temporarily installed in HRAM `$FFF3`
    (`HelperOn`/`HelperOff`, original bytes saved in `HR_BACKUP`).
* Map LCD-on restores `MAP_THEME` (set by `Slot`), so closing the menu or a dialog brings the area
  colours back.

## Known limits
* On theme-0 maps (overworld, castle) item palettes keep their own colour 0, so the A/B icons sit
  on a small tinted square (wood = peach, stone = grey) inside the cream panel. Cavern/menu themes
  share colour 0 and show no square.
* Gold digits are shade 3 only, so they are drawn in the palette's darkest colour (dark brown).
* Dropping/using an item leaves the old palette on the now empty slot (invisible: empty slots show
  only colour 0).
