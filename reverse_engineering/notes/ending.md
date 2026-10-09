# End game, attract loop, death and other story screens (run 6)

Evidence: PyBoy frame-by-frame recordings (a frame every 5-15 frames) of the original and DX
from `save_states/{og,dx}_cavern_*.state` (written by `scripts/capture_screens.py`), with
`rst $28` / LCD-on site logging, memory pokes and forced jumps at the main loop
(0:`$1EF6`); the mgbdis disassembly. Before/after contact sheets (outside the repo):
`/workspace/ultima-rov-dx-ending/contact_sheet*.png` (original | DX fed12a1 | DX now).

## How the ending is triggered
* `$D135` (WRAM) = runes reclaimed, one bit per rune. The main loop at 0:`$1F0D` tests
  `[$D135] == $FF` (all eight). Single player (`$C511 = 0`) and not yet shown (`$D1F4 = 0`):
  `$D12F = 0`, `$D1F4 = 1`, `$C7EB = [$D133]` (champion), music `$23`, `call 7:$4A2A`, then
  `jp 0:$1AE6`. 2-player games go through 3:`$6EF1` (`$C7E3 = $FF`, 0:`$19CD`, 7:`$4A2A`).
* The final Black Knight fight just leads to the last rune; there is no separate boss flag.
  Reproduce: any in-game state, poke `$D135 = $FF`, run one main-loop pass.

## Ending sequence (bank 7)
| Site | LCDC | Screen |
|---|---|---|
| 7:`$4A40` | `$81` | text (bank 7 `$7F5D`): "Congratulations! You have foiled the Black Knight, and returned the eight Runes of Virtue. Lord British summons you to his throne room to be Knighted." Waits for a button. |
| 7:`$4AE3` | `$87` | throne-room picture (tiles 7:`$6F00`, map 7:`$7400`): the champion walks in from the left (OBJ palette 0, follows `$D133`) and kneels; Lord British (BG) raises his sword (metatile `$60` at `$9990` via 0:`$066B`); "THE END" in row 8 (tiles `$70-$74`). A button after THE END. |
| 0:`$1804` -> 7:`$4C32` | | the attract loop (below) |

## Attract loop (after the ending and after "Quit for now")
`4C32` "FCI, Origin, and PonyCanyon Inc Present / A Lord British Game / Ultima: Runes of Virtue /
(c)1991 Origin / Licensed by Nintendo" -> 7:`$44F2` castle title with lightning (`$4517/$457E/$4589`,
LCD already on) -> logo 7:`$4BC2` -> 7:`$4C78` "Ultima: Runes of Virtue By Gary Scott Smith and
Dr. Cat" -> 7:`$4C8D` staff (Art: 'Manda Dee and Denis Loubet; Music and Add'l Design: 'Manda Dee;
Dungeon Music: The Fat Man; Creative Director: Richard Garriott; Producer: Jeff Johannigman;
Executive Producer: Dallas Snell) -> 3:`$6E93`/`$6EE1` One / Two Player High Scores ->
7:`$4853` (LCDC `$E7`) the parade: "YOUR FRIENDS" (Lord British, Sherry, Chuckles, Dr. Cat, Gnu Gnu,
Beh Lem, Ariana, Kador) and "YOUR FOES" (Trolls, Ghosts, Gremlins, Slimes, Skeletons, Snakes, Rats,
Wizards, Reapers, Wisps, Jaggers, Cyclops), sprites scrolling in on OBJ palette 0 -> `4C32` again.

### Parade sprites
* Five lists of 4 graphic bytes + `$FF` at 7:`$7CA6` (`8C 80 B0 9C`, `96 9E 9A 8E` friends;
  `22 04 0E 0C`, `1A 2C 14 A4`, `02 08 20 34` foes). Bit 7 = people bank (1:`$5A92`), else
  monsters (6:`$6AD9`); source = (byte & `$7F`) * `$40`, so the gameplay sprite id is
  (byte & `$3F`) | (bit 7 >> 1): `$A4` wizard = `$64` (brigand, folk), `$80` Sherry = `$40`, `$8C` Lord British = `$4C`.
* 7:`$49EE` (DE = list, HL = `$8800`) loads list entry k into tiles `$80+8k` through 0:`$1811` (its
  only caller); it is called from 7:`$47F7` (first page, before the LCD-on at 7:`$4853`) and 7:`$48D4`
  (7:`$48C8`, each next page; the LCD stays on). Sprite k = OAM entries 2+2k, 3+2k (8x16), tiles
  `$80+8k..` (0:`$083D` animates by +-4). The game never touches `$C539`/`$C580` here: after
  "Quit for now" or the ending they still hold the last area's sprite slots.
* Why the DX showed them uncoloured: `OamPass` takes the palette from the loaded sprite slots
  (`$C539` count, `$C580` ids). On the parade the count is 0 after power-on, so every sprite
  fell to `UnloadedPal` = OBJ palette 0 (folk-brown `scene_obj.parade`); after a game the stale
  slots gave the parade sprites the last area's palettes instead.
* Fix: both `call $49EE` go through bank-7 `ParadeLoad` (7:`$7FF8`, `$FF` padding), which stores
  the list's low byte in HRAM `$FF9C` (unused HRAM, so DMG behaviour is unchanged) and jumps on.
  At the parade's LCD-on, bank-8 `SceneHook` (return address `$4854`) copies `PARADE_PAL_ROM`
  (builder: OBJPAL of each list byte, so foes get `monster` = tier-0 green, Lord British and Gnu
  Gnu `royal`, the wisp `item`, the rest `folk`) over `ENTRY_TIER` (unused off map screens) and
  sets `PARADE_ON` (`$FF9D`); `TierClear` ends it at the next LCD-on. `OamPass` reads the slot count
  through `SlotCount`, which on the parade colours the entry with `PARADE_TAB[$FF9C - $A6 + slot]`.
  Verified with PyBoy and the SameBoy harness (idle from power-on to the parade, ~2,460 frames;
  OAM palettes 5,5,4,4.. / 1,1,1.. per page; blocked VRAM/CRAM/OAM writes identical to the previous build).
  DMG frames are identical to the previous build.

## Death
* Damage (0:`$33FC`) writes HP to `$D127` (max `$D128`). At 0 in single player: 0:`$3460` ->
  0:`$17D8` -> 7:`$4276`: skull and crossbones with twinkling star sprites (site 7:`$4319`, LCDC `$83`,
  OBP0 = `$1B` set after LCD on), waits for a button -> 7:`$438B` blank -> 0:`$1323` Lord British:
  "Thou hast fallen in battle! Wouldst thou continue with thy quest? Continue / Quit for now".
  Continue reloads the map (0:`$03A3`, `$23E2`); Quit goes to the attract loop.
* Reproduce: poke `$D127 = 0` and jump to 0:`$3460` from the main loop.

## Rune reclaimed
* 0:`$0A14` with A = item id (`$24`+): 0:`$3F9C` copies the rune icon (bank 3 `$5400` -> `$8F80`),
  then 7:`$4000`: shrine picture (site 7:`$40BF`, LCDC `$87`), marble pillars and light from above;
  the champion walks up and raises the rune (BG tiles `$2E/$2F` at `$9969`); the flash toggles to the
  `$9C00` map filled with tile `$E6` (SCX `$10`).
* Then the text screen 0:`$0AEB` "You have reclaimed the rune of Honesty! You have gained
  Intelligence!" (bank 1 `$7EF1`) with the side panel. It was classified as a map site: the DX
  showed map colours (blue blocks behind spaces); now a dialog site (`$6D`).

## Other story screens (2-player / link cable only)
| Site | Screen | Status |
|---|---|---|
| 0:`$14FF` (routine 0:`$14BD`, from 0:`$1C11`, 1:`$41A1`) | "Please wait for <name> the <Mage/Bard/Fighter/Ranger>." (bank 1 `$7F98`) + side panel, 16 frames | was a map site; now a dialog site. Verified by force-calling 0:`$14BD` |
| 3:`$6F78` / `$6FAC` (via 3:`$6EF1`) | "This Game's Over / Your Score / Other Player" (3:`$7BB5`) | text mode, not reached |
| 3:`$71FF` / `$720E` (LCDC `$89`) | "Please wait" (3:`$7F22`) | text mode, not reached |
| 3:`$79FC` / `$7A21` (LCDC `$91`) | short flash routines, no direct callers found | not reached |
| 1:`$4126`, 1:`$54E9` | 2-player start (serial) / unknown | map mode, not reached |

## Picture tiles (DX LUTs, `bg_tile_categories.yaml` scenes)
* Throne: windows `$00-$13` (panes `$01/$02`); banner `$04-$07`; ankh `$14-$16,$1B-$1D,$20-$22,$25,$28`;
  wall bands `$18-$1A,$1E,$1F,$23,$24,$26,$27,$29`; floor `$2A`; banner foot `$2B-$2F`; throne and
  Lord British `$31,$32,$35-$41`; steps `$42-$4B,$4D-$4F`; bottom floor `$4C`.
* Shrine: pillars `$00/$01/$03-$05/$0B-$11` and mirrored `$30/$31/$33-$35/$3B-$41`; light bands
  `$02,$06-$0A,$32,$36-$3A`; floor `$12-$22,$42-$52`.
* Skull: background `$00/$50`; skull and bones `$01-$4F` and mirrored `$51-$A1`.

## Colorization (DX)
* `SceneTramp` (WRAM2) runs at every game LCD-on before the CRAM sync; bank-8 `SceneHook` looks the
  `rst $28` return address up in `SCENES` (lo, hi, ROM theme, LUT, OBJ) and replaces the theme
  (`CUR_THEME = $FE`: the next screen reloads its own), the tile LUT (`SCENE_LUTS`) and OBJ palette 0
  (`SCENE_OBJ`). The caller's ROM bank is found again from its byte at `$4001` (`BANK_SIG`).
* Themes (`rov_palettes.yaml` bg_themes): `shrine` lavender marble, golden light, blue-violet
  steps, fire-red rune; `royal` cream vellum, royal purple ink (ending text); `throne` warm stone,
  sky windows, crimson banner with a gold ankh, marble floor, gold throne and Lord British in red,
  carpeted steps; `death` bone on blood-black, stars white/gold (`scene_obj.stars`); `credits` night
  blue with cream letters (4C32/4C78/4C8D); `scores` ledger green; `parade` pale sky paper, slate ink;
  its sprites take their gameplay palettes (Parade sprites above; `scene_obj.parade` is only OBJ palette 0).
* Title cards: theme byte `$FF` keeps the entrance theme and loads the UI palette from
  `CARD_TINT[$FF8F]` (the card number, 7:`$4608`): 1 Hatred navy (unchanged), 2 Deceit blue,
  3 Cowardice red, 4 Injustice green, 5 Dishonor purple, 6 Selfishness orange, 7 Pride grey,
  9 the Great Stygian Abyss ember red (`rov_palettes.yaml card_tints`).
* Gold amount: digits `$E8-$F1` are solid colour-3 glyphs (font 3:`$4A00`). On map screens
  SceneHook copies a gold redraw (colour 1 body, colour-3 drop shadow) to VRAM bank 1 `$8E80`
  and `LUT_GAME` gives those tiles attribute `gold | $08` (tile data from bank 1).
