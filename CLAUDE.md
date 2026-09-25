# CLAUDE.md

Guidance for Claude Code (and other agents) working in this repository.
Read `AGENTS.md` first; its rules are mandatory.

## Project

Ultima: Runes of Virtue DX is a Game Boy Color colorization of the DMG game
**Ultima: Runes of Virtue (USA)** (Origin Systems; FCI; 1991/1992). Sibling
project and template: `penta-dragon-dx` (GBC colorization of Penta Dragon).

**Current state:** scaffold. No ROM has been supplied yet and no reverse
engineering has been done. Every game-specific fact is `None`/TODO in
`src/ultima_rov_dx/game_layout.py`.

## Approach (inherited from penta-dragon-dx)

- Pure-Python binary patcher, no assembler toolchain (no RGBDS). Builders
  load the verified original ROM and palette YAML, hand-assemble SM83
  routines (`src/ultima_rov_dx/asm.py`), write them into free ROM space,
  and install hooks with exact preimage checks.
- Header CGB flag 0x143 = 0x80 (CGB-enhanced, still DMG-compatible); header
  and global checksums recomputed.
- Colors live in YAML (`palettes/`). Distribution is a ROM-free IPS patch.
- Verification is emulator-driven: mGBA (via the single-flight guard) is the
  authority for pixel/timing questions; PyBoy is fine for quick headless
  probes and memory dumps but does not enforce VRAM/OAM access windows.

## Where things live

| Path | Purpose |
|---|---|
| `scripts/build_dx.py` | Production builder (stages 1–5; fails closed) |
| `scripts/check_rom.py` | ROM presence/hash check + header dump (no deps) |
| `src/ultima_rov_dx/original_rom.py` | Expected ROM path, known hashes, exit codes |
| `src/ultima_rov_dx/game_layout.py` | **All** game-specific addresses/hooks (TODO) |
| `src/ultima_rov_dx/{rom_utils,patch_builder,asm,palettes}.py` | Generic ROM/IPS/asm/palette helpers |
| `src/ultima_rov_dx/cli.py` | `rov-dx` CLI: check-rom, verify, analyze, check-palettes, build-patch |
| `scripts/launch_mgba.sh`, `scripts/mgba_singleflight.py`, `scripts/mgba-*-singleflight` | Guarded emulator launching |
| `scripts/launch_gate.py` | PyBoy boot check before headed play |
| `scripts/diagnostics/` | Guard verifier, pre-commit policy; future gates |
| `scripts/probes/`, `scripts/lua/` | Future PyBoy / mGBA-Lua probes |
| `reverse_engineering/notes/` | RE notes; start with `TODO.md` |
| `docs/` | `INDEX.md`, `rom_facts.md`, `release/` |

## Exit codes

- 66 original ROM missing, 65 wrong/unsupported dump (sysexits)
- 78 builder needs reverse-engineering facts that are still unknown
- 75 another guarded emulator owns the single-flight slot

## Pitfalls to keep in mind (generic CGB colorization)

1. CGB mode ignores BGP/OBP0/OBP1. A CGB-flagged ROM that never writes CRAM
   shows a blank screen — the first real milestone is a palette-init hook.
2. CRAM and VRAM bank 1 (attributes) are inaccessible during mode 3; write
   them in VBlank/HBlank or with the LCD off.
3. Hooks that add DI windows or VBlank work change timing and audio; measure
   speed parity against the original, don't assume.
4. Always verify hook preimages byte-for-byte; never patch a ROM whose hash
   is not the supported dump.
5. Do not copy Penta Dragon addresses or state variables; nothing carries over.
