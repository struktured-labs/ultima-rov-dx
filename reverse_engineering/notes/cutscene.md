# Dungeon entrance: title card and cutscene (run 3)

Evidence: PyBoy frame-by-frame recordings from `save_states/{og,dx}_cavern_approach.state`
(one cell below the Cavern of Hatred mouth, written by `scripts/capture_screens.py`),
`rst $28` site logging, VRAM/OAM dumps in the cutscene, the mgbdis disassembly of bank 7.
Reproduce the frames with `scripts/capture_entry_sequence.py`.

## Sequence (DX frame numbers after the step up; the original runs ~10 frames later)
| Frames | LCD-on site / LCDC | What |
|---|---|---|
| 0-11 | - | overworld scrolls one cell up |
| 12 | 0:`$1804`, `$8F` | LCD switched "on" while already on (DX handler skips it): one garbled frame of stale text-box tiles, **in both builds** (the game's own glitch) |
| 13-22 | BGP `$00`, LCD off | blank |
| 23-112 | 7:`$4619`, `$8F` | **title card** "The Cavern of Hatred" (bank 7 `$4602`; text ptr `$7C24`/`$7C89`), HUD at the right |
| 113-122 | 0:`$03A3` (map, 2 frames), LCD off | blank |
| 123-381 | 7:`$4692`, `$87` | **cutscene**: cliff with the cave mouth, violet mountains, misty plain, rocky ground with bones; the champion walks in from the right and into the cave |
| 382-396 | 7:`$438B`, `$80` | blank |
| 397 | 0:`$23E2` | area `$18` map (level 1) |

Pressing any button while the title card is up skips the card **and** the cutscene (both builds):
bank 7 calls `$184A` with `c=$5A` (wait up to $5A frames, NZ if a button was pressed) and on NZ
jumps past the cutscene (map restore, `$438B` blank, area entry). Buttons during the cutscene do nothing.

## How the cutscene is drawn (bank 7 `$4620-$46EB`)
* LCDC `$87`: BG tiles `$8800` (signed), map `$9800`, 8x16 OBJ, OBP0 = `$34`
  (index 1 -> shade 1, 2 -> shade 3, **3 -> shade 0**: the hero's white parts use shade 0).
* Saves VRAM `$8000-$83FF` / `$8C00-$8FFF` into WRAM bank 1 `$D800` / `$DC00` and shadow OAM
  `$C000` into `$D700`; restores them afterwards (`$46BC`).
* Art: tiles bank 7 `$5D50` -> `$9000` and `$6550` -> `$8800`; tile map from `$6B90` (via `$45B4`);
  sprites via `$6CF8` -> `$C000`. The hero graphic (tiles `$00-$0E` at `$8000`) follows the champion
  `$D133` (`$46EE`).
* One fixed picture, shared by all dungeon entrances. BG tile ids `$00-$E3` are numbered in reading
  order with duplicates reused (`$05` = sky, `$0C`/`$4F` = cliff fill, `$1E` = solid colour 1,
  used both as a mountain top (row 3) and at the ground's right edge (row 13, col 19)).
* DMG colours by material: sky = colour 0; mountains, misty plain and ground = colour 1 (dither
  over 0 for the plain); cliff and rocks = colours 2-3.
* The map is static while the hero walks (only OAM changes), so attributes computed at LCD-on hold.

## Colorization (DX)
* Mode bytes after `rst $28`: `$49` title card (text LUT + `entrance` theme), `$52` picture
  (`PICTURE_LUT` from bank 8 + `entrance` theme + per-cell `PICTURE_FIX`), `$5B` blank
  (UI colour 0 forced to `FLAT_BG` white). Sites in `game_layout.CARD/PICTURE/BLANK_LCD_ON_SITES`.
* `entrance` theme (`rov_palettes.yaml bg_themes.entrance`): UI = navy card, gold letters and HUD;
  picture palettes share colours 2-3 (cliff browns), so the tile palette only picks colour 1:
  earth (cliff), stone/gold (violet mountains), grass (misty green plain), wood (ochre ground);
  colour 0 is the sky, banded rose (fire, rows 0-1) / peach (gold, rows 2-3) / cream (rest).
* OBJ colour 0 is white in every OBJ palette (was black): with OBP0 `$34` the hero's white parts
  map to shade 0; sprites never show colour 0 otherwise (transparent).
* Flat DMG palettes (`$00/$55/$AA/$FF`) make every CGB palette the same `FLAT_BG` colour: no
  mosaic of per-palette colour 0 on blank frames.
* The area theme comes back when level 1 loads its metatile slots.

## Other transitions checked
* Exit back to the overworld (level 1 up-ladder, cell `$66`): LCD off -> overworld redraw at
  `$23E2`, no card or cutscene; theme 0 returns, no flashes.
* Ladder `$18` -> `$19`: LCD off -> map, no card; cavern theme kept.
* The other `$87` sites are the rune shrine (7:`$40BF`) and the ending throne room (7:`$4AE3`); both get
  scene themes and picture LUTs (ending.md). Title cards are tinted per dungeon (`card_tints`).
