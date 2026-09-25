# Reverse-engineering backlog

Nothing below is known yet. Each item, once established, must be recorded in
`src/ultima_rov_dx/game_layout.py` **with a citation** to the note/probe that
proved it (static disassembly offset list, emulator trace, etc.).

## 0. Prerequisites
- [ ] User supplies `rom/Ultima - Runes of Virtue (USA).gb`; `python3 scripts/check_rom.py` passes.
- [ ] Record header title, cartridge type (MBC), ROM/RAM size codes, SGB flag in `docs/rom_facts.md`.
- [ ] Choose a disassembler/debugger workflow (e.g. mGBA debugger + Lua via the guarded wrapper; optional: mgbdis for a static disassembly kept outside git if it embeds ROM bytes).

## 1. Minimum viable color (first milestone)
- [ ] Boot path: entry at 0x0100 → init → LCD on. Find a point after LCD init / before the title draws → `PALETTE_INIT_HOOK` (+ exact preimage bytes).
- [ ] Bank switching: MBC register writes and the RAM/HRAM shadow of the current bank → `BANK_SELECT_SHADOW`.
- [ ] Free space per bank (`uv run rov-dx analyze --rom ...`), confirm it is truly unused (not data read by index) → `FREE_SPACE`.
- [ ] Install static CRAM load (`asm.cram_loader`) so the CGB-flagged ROM is no longer blank. Pass `scripts/launch_gate.py`.

## 2. Scene awareness
- [ ] Scene/state variable(s): title, character select (Mage/Bard/Knight/Ranger), overworld, towns/castle, each of the 8 dungeons, 2-player mode, ending → `SCENE_STATE_ADDR`.
- [ ] VBlank ISR entry and timing budget → `VBLANK_HOOK`.
- [ ] Does the game use DMG palette fades (BGP/OBP writes) for transitions? Those must be mirrored into CRAM.

## 3. BG attributes
- [ ] Map/tile pipeline: where map tiles are written to the BG tilemap(s) (0x9800/0x9C00), scroll handling, window layer usage (status bar/text boxes) → `TILEMAP_WRITER_HOOKS`.
- [ ] Tile set per scene → `palettes/bg_tile_categories.yaml`.

## 4. Sprites
- [ ] Shadow OAM buffer and HRAM DMA routine → `SHADOW_OAM`, `OAM_DMA_HRAM`.
- [ ] Sprite tile ranges for player characters, enemies, projectiles, items.
- [ ] Does the game use OAM priority / DMG OBP1? (OAM attr bit 4 has no meaning on CGB; bits 0–2 select CGB palette.)

## 5. Verification harness (port from penta-dragon-dx as needed)
- [ ] Deterministic double build + receipt.
- [ ] OG-vs-DX speed parity on main-loop counters.
- [ ] Per-scene capture gates (mGBA authoritative).
