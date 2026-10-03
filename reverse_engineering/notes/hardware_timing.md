# Hardware timing (VRAM / palette / OAM access)

DX runs in CGB double speed (bank-8 boot: KEY1 + `stop`). Writes to VRAM in
mode 3, to BCPD/OCPD in mode 3 and to OAM in modes 2-3 are dropped by real
hardware. PyBoy does not model this, so it is checked with an instrumented SameBoy
core (`tools/sameboy_harness`, `scripts/hw_access_scan.py`). The core's own
`vram_write_blocked` / `cgb_palettes_blocked` / `oam_write_blocked` flags are logged
for every CPU write, with LY, STAT mode, speed and PC.

Scan route: boot to the throne room, then teleport into Valor cavern rooms 2C/27,
Selfishness 4A, 3D, 49, 4C and the overworld. Wander, attack and open the start menu in
each, about 11,200 frames per run (SameBoy git 213a12c, CGB-E model, SameBoy boot ROM).

| build, speed | VRAM blocked | BCPD/OCPD blocked | OAM blocked (CPU writes) |
|---|---|---|---|
| original DMG game (CGB compat, single) | 0 / 18,736 | 0 | 0 |
| DX 1458482 (HEAD before this pass), double | 3,184 / 55,759 | 0 | 436 / 53,284 |
| DX this pass, double | **0** / 69,748 | **0** | 36 / 983 (2 title-cutscene frames) |
| DX 1458482, single speed (stop patched out) | 3,587 | 209 | 17,271 |
| DX this pass, single speed (stop patched out) | 3,644 | 229 | 47 |

## What was wrong

The game's VBlank interrupt (0:`$1ACB`) or its main loop (0:`$1EF3`, right after the
halt wait) calls the OAM DMA at the start of VBlank. The game then does its own
VBlank VRAM work, for example the animated-tile copy of 64 bytes at 0:`$176A`
(after 0:`$1717` waits for LY 145 and DMAs). DX's DMA hook ran the 40-entry OAM
palette pass, the side-panel live refresh, `LiveFloor` and the tier scan inside
that window. That took about 8,000 T-cycles (single-speed units, VBlank =
4,560). The game's copy started around LY 7, and the hook's own OAM writes at
LY 0-1 were dropped. On hardware this means torn animated tiles (water/lava frames) and
monsters keeping the wrong palette for a frame.

## Fix

* Sprite palettes are computed at the game's idle waits (`Prep8`, see monsters.md):
  the main loop's halt wait 0:`$1EE7`, the VBlank-flag wait 0:`$02EA`, and the animated-tile
  copy's wait 0:`$175A` (`call $02DC` → `call PrepWait`: prep, then the original wait). They
  are written into the shadow OAM, so the DMA carries them. The hook skips its OAM pass after
  a prep.
* Trampoline `PrepTramp` lives in interrupt-vector padding the game never executes:
  `$0043-$0047` and `$004B-$004F` after the VBlank/STAT jumps, `$0051-$0057` after the
  timer `reti`, and `$005B-$005F` after the serial jump. `PrepWait` uses the rst `$20`/`$28`
  padding (`$0023-$0027`, `$002B-$002D`). The timer and joypad
  interrupts are never enabled (the only IE write is `$0B`).
* The hook's live refresh runs only when it starts by LY 145, so a late DMA (0:`$1717`)
  leaves the game its time for the tile copy.

Hook timeline in Valor 2C (T-cycles from VBlank start, medians):

| | before | after |
|---|---|---|
| DMA done | 510 | 510 |
| OAM pass ends | 3,708 | skipped (prep) |
| live refresh / panel cells | 3,724-5,188 (cells mostly skipped: past VBlank) | 656-2,600 |
| hook returns | about 8,000 | about 2,700 |

Side-panel refresh went from 1,519 to 2,260 cells per 600 frames.

## Residual

* The routine 0:`$02DC` (wait for LY 145) is not hooked itself. The title code calls it
  back-to-back inside line 145, where the original returns at once. With a hook there (even a
  ~55 M-cycle skip path), 306 of 310 such calls missed LY 145 and waited a frame, which slowed
  the title sequence by about 13% (SameBoy, first 1,300 frames: 1,063 vs 1,217 wait exits).
  Only its call from the animated-tile copy (0:`$175A`) is hooked; the title wait counts now
  match the previous build exactly (1,232 entries / 1,217 exits).
* 36 OAM writes in 2 frames of a bank-7 title cutscene, which waits through 0:`$02DC` directly
  (no prep), so the fallback pass ran late.
* Gameplay pace: SameBoy main-loop iterations over 854 frames are identical to the previous
  build in Valor 2C/27 and Selfishness 4A; on the overworld 741 vs 693 (fewer lag frames, the
  shorter VBlank hook). PyBoy's scripted regression walk (`capture_screens.py`) therefore runs
  one frame ahead from the story → overworld transition, monster positions differ, and its
  frame-timed cavern route ends in a death screen. That route needs re-tuning; it is not a
  game bug.
* Single speed is not a supported mode. DX always switches to double speed on CGB/GBA,
  and its VBlank work does not fit at single speed (the table rows are for reference only).
* The game's own non-VBlank writes are unchanged: the original writes no VRAM outside VBlank.

## Gambatte

Debian's `libretro-gambatte` (0.5.0+git20160522) boots the ROM headless in CGB mode
through a small ctypes libretro host, and the title renders correctly. It exposes no VRAM
and no hooks, and frame-exact comparison with PyBoy is not possible (different boot
timing, title RNG), so SameBoy is the oracle.
