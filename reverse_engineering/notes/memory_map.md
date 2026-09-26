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
| `$D12F` | area/map id (02 overworld, 00 Lord British's castle) |
| `$D800-` (bank 1) | generated tile program |
| `$FF80-$FF8B` | OAM DMA routine |
| `$FF8E` | VBlank-happened flag |
| `$FFA0-$FFAF` | metatile slot -> graphic index |
| free | `$FF98-$FF9F`, `$FFE8-$FFFE` (DX uses `$FF98-$FF9B`) |
| WRAM bank 2-7 | unused by the DMG game (DX runtime lives in bank 2) |

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
