# Memory map and core routines (Ultima: Runes of Virtue, USA)

Evidence: mgbdis disassembly of the verified ROM (kept outside git),
PyBoy traces (`tmp/hooks.py`, `tmp/lcdtrace.py`), and the
`scripts/probes/sm83.py` interpreter. Canonical values: `src/ultima_rov_dx/game_layout.py`.

## Boot
| Addr | What |
|---|---|
| `$0100` | `nop; jp $0150` |
| `$0150` | `jp $1AE2` (**DX hook: `jp Boot`**) |
| `$1AE2` | `di`, SP=`$CFFF`, init, LCDC=`$E7`, main loop around `$1B7B` |
| bank3 `$7008` | clears WRAM `$C000-$DFFF`, copies 12-byte OAM DMA routine bank3 `$735C` -> `$FF80` |

The game writes the MBC2 bank register (`$2100`) directly and keeps **no bank shadow**;
every routine that needs a bank selects it itself. The DX runtime therefore always
restores bank 1 (the only bank the hooked callers run from) after far calls.

## Interrupts
* VBlank ISR `$1ACB`: `push af`; if `[$C522] != 1` then `call $FF80` (OAM DMA); sets `[$FF8E]=1`.
* STAT ISR `$1A9F`: link/serial pump; touches only `$C5xx/$CCxx/$C7EC`.
* OAM DMA (`$FF80`) is also called directly from `$03A8 $10D3 $1762 $1AD3 $1EF3 $2BE5`,
  bank1 `$50C0 $52C3 $52F3`. All run in VBlank (after `$02DC` wait-LY-$91) or with the LCD off.

## WRAM / HRAM
| Addr | Use |
|---|---|
| `$C000-$C09F` | shadow OAM; also dialog text buffer while `$C522=1` |
| `$C100-$C4FF` | shadow of BG map `$9800-$9BFF` |
| `$C511` | overworld flag |
| `$C522` | 1 = VBlank ISR must not DMA (tile program running, dialogs) |
| `$C580-$C58F` | sprite graphic id per sprite slot (bit7 large, bit6 people, `$FF` = continuation) |
| `$C600-$C6FF` | current area map, 16x16 cells (bits 0-5 graphic g, 6-7 flags), see dungeons.md |
| `$D12F` | area/map id (02 overworld, 00 Lord British's castle, 18/19/1A Cavern of Hatred) |
| `$D133` | champion: 0 Mariah, 1 Iolo, 2 Dupre, 3 Shamino (select cursor too); 2-player partner `$D173` (see heroes.md) |
| `$D800-` (bank 1) | generated tile program |
| `$FF80-$FF8B` | OAM DMA routine |
| `$FF8E` | VBlank-happened flag |
| `$FF91` | player cell in the area map (high nibble row, low nibble column) |
| `$FFA0-$FFAF` | metatile slot -> graphic index |
| free | `$FF98-$FF9F`, `$FFE8-$FFFE` (DX uses `$FF98-$FF9D`: `$FF9C` PARADE_LIST, also written on DMG; `$FF9D` PARADE_ON) |
| WRAM bank 2-7 | unused by the DMG game (DX runtime lives in bank 2) |

## LCD-on sites seen (PyBoy hook on the DX `rst $28`)
`$03A3` map restore after dialogs/menus (also passes during title/story), `$1B17` overworld,
`$23E2` area entry, `$10A8` start menu (stats + mini-map), `$1323` dialog box,
bank 3 `$78F8/$7954/$79C7` champion select, `$7665/$7697/$7A93/$7AA2/$7779/$7788` story,
initials, difficulty; bank 7 `$4319/$438B/$4619` blank transition screens and game over; 0:`$1804` (LCD "on" while on),
7:`$4619` dungeon title card, 7:`$4692` entrance cutscene (LCDC `$87`), 7:`$438B` blank (see cutscene.md).
End game, death, rune shrine, credits (ending.md): 7:`$40BF` rune shrine, 0:`$0AEB` rune text (dialog), 7:`$4A40` ending text,
7:`$4AE3` throne room, 7:`$4C32/$4C78/$4C8D` credits, 3:`$6E93/$6EE1` high scores, 7:`$4853` parade, 7:`$4319` death screen,
0:`$14FF` 2-player wait (dialog, forced only).

## Game variables (end game)
`$D135` runes reclaimed (bitmask; `$FF` = all eight starts the ending), `$D1F4` ending shown, `$D127`/`$D128` HP / max HP,
`$D173` class of the fallen 2-player partner, HRAM `$FF8F` text parameter (the title-card dungeon number, 1-7, 9 = Abyss).

## DX runtime variables (WRAM bank 2)
`$D700-$D702` last BGP/OBP0/OBP1, `$D703` LCD mode (0 map, 1 castle, 2 text, 3 picture, 4 menu, 5 dialog, 9 logo),
`$D704` current theme, `$D705` entrance theme, `$D706` last mode byte, `$D707` map theme, `$D708-$D70F` `FLAT_BG`,
`$D710` UI theme, `$D711/$D712` live-refresh counters, `$D716` MAP_CACHED, `$D717` HERO_CACHED (champion in OBJ palette 0), `$D718` menu cursor colours, `$D720` HRAM backup (12),
`$D740` `ITEM_PAL` (64), `$D780` inventory copy (64), `$D7C0` REC_TIER (16, colour tier per object record), `$D7D0` ITEM_CACHE (15, floor items `$C5B0+k` last coloured), `$D7DF` PREP_DONE (shadow OAM coloured by Prep8 since the last DMA), `$DB10` ENTRY_TIER (40, tier per OAM entry), code section `wram2c` at `$DB40-$DBFF` (see monsters.md). Tables `$DC00` `LUT_MENU`, `$DD00` `LUT_GAME` (`$DD00-$DD1F` = HERO_BG portrait colours), `$DE00` `BG_THEMES` (8x64).
HRAM `$FFF3-$FFFE`: WRAM1 reader installed only while used (see menu.md).
Bank 8: `$5600` PICTURE_LUT, `$5700` PICTURE_FIX, `$5C00` LUT_TITLE, `$5D00` LUT_LOGO, `$6000` BRAND_TILES, `$6600` BRAND_CELLS,
`$6800` AREA_THEME (512: `$D13E` = 0, then 1), `$6A00` METAPAL (16 sets x 128), `$7200` THEME_BG_ROM (32 x 64), `$7A00` THEME_OBJ_ROM (32 x 8),
`$7B00` RT_SLOT (WRAM slot per theme), `$7B20` MP_IDX (METAPAL set per theme), `$7B40` HERO_OBJ_ROM (4 x 8, player palette per champion).
Scenes (ending.md): `$5800` SCENE_LUTS (4 x 256), `$5E00` SCENES ((ret lo, ret hi, ROM theme or `$FF` = card tint, LUT, OBJ)*, hi = 0 ends),
`$5F00` SCENE_OBJ (8 per scene OBJ palette 0), `$5FF0` BANK_SIG (byte at `$4001` of banks 1-7), `$7C00` CARD_TINT (16 x 8, title-card UI palette per `$FF8F`),
`$7C80` CARD_UI (low byte of BASE_BG's UI palette), `$7D00` GOLD_DIGITS (160: side-panel digits `$E8-$F1` in gold for VRAM bank 1 `$8E80`),
`$7E00` PARADE_PAL_ROM (25: OBJ palette per byte of the parade lists 7:`$7CA6`, copied over ENTRY_TIER while the parade is up; ending.md).
Bank 7: `$7FF8-$7FFD` ParadeLoad (`$FF` padding after the ending text).
Bank 2: `$7F34-$7FB9` AllocHook (allocator `$5FE6` hook), `$7FBA` TIER_TAB (70: tier nibble per template). Object records `$D000-$D0FF` (WRAM1, 16 bytes; monsters.md).
Inventory/side panel: `$D100-$D11F` bag, `$D125` B item, `$D126` A item, `$D134` armour (see menu.md).

## Palettes
BGP is `$E4` normally, `$00` while blanking during transitions. OBP0 `$E4`-ish; OBP1 is
`$1B`/`$A8` on the title and `$00` in gameplay. Fades are done by writing BGP/OBPx,
so the DX runtime re-derives CRAM whenever those registers change.

## Useful routines
`$01A0` memcpy HL->DE BC; `$01A9` wait LY $91 then copy 64 bytes DE->HL;
`$02DC` wait LY==$91 (returns immediately with LCD off); `$078F`/`$079D` LCD off;
`$066B` write one 2x2 metatile (A=t, HL=map) returning HL+$21, A=t+4;
`$1512` restores the map after a dialog.

## Free ROM space
Bank 0: `$0003-$0037` (rst vectors, unused) and `$0061-$00FF`. `$0038` is kept (rst $38 = crash
trap on `$FF`). The DX build expands the ROM to 256 KiB (header `0x148=$03`, MBC2 max) and
uses bank 8; banks 9-15 are free. The expanded ROM was verified to boot and play identically in DMG mode.

### Idle-wait prep (hardware timing)

* ROM0 `PrepTramp` in vector padding (`$0043-$0047`, `$004B-$004F`, `$0051-$0057`, `$005B-$005F`),
  called from 0:`$1EE7` (main loop halt wait), 0:`$02EA` (VBlank-flag wait) and, through `PrepWait`
  (`$0023`/`$002B`), 0:`$175A` (animated-tile copy). 0:`$02DC` itself (wait
  LY 145) is deliberately not hooked: the title code re-enters it inside line 145, so any
  overhead costs a frame.
* WRAM2 `W2Prep` → bank 8 `Prep8` (section `bank8b`, `$5400-$55FF`, between the WRAM2 image and
  `PICTURE_LUT`), also `FillAttrs8` (moved out of WRAM2; it also applies the entrance-cutscene
  `PICTURE_FIX` cells since the parade fix). TierFar modes: C = 0/`$80` tier scan,
  1 HeroMenu8, 2 Prep8, 4 FillAttrs8.
* `OamPass` (WRAM2) = the OAM palette loop, over `$FE00` (hook fallback) or `$C000` (Prep8).
