# Reverse-engineering backlog

Run 2 (2026-09-26) resolved most items; see memory_map.md, bg_tiles.md, sprites.md, colorization_design.md. Each item, once established, must be recorded in
`src/ultima_rov_dx/game_layout.py` **with a citation** to the note/probe that
proved it (static disassembly offset list, emulator trace, etc.).

## 0. Prerequisites
- [x] User supplies `rom/Ultima - Runes of Virtue (USA).gb`; `python3 scripts/check_rom.py` passes.
- [x] Record header title, cartridge type (MBC), ROM/RAM size codes, SGB flag in `docs/rom_facts.md`.
- [x] Choose a disassembler/debugger workflow (e.g. mGBA debugger + Lua via the guarded wrapper; optional: mgbdis for a static disassembly kept outside git if it embeds ROM bytes).

## 1. Minimum viable color (first milestone)
- [x] Boot path: entry at 0x0100 → init → LCD on. Find a point after LCD init / before the title draws → `PALETTE_INIT_HOOK` (+ exact preimage bytes).
- [x] Bank switching: MBC register writes and the RAM/HRAM shadow of the current bank → `BANK_SELECT_SHADOW`.
- [x] Free space per bank (`uv run rov-dx analyze --rom ...`), confirm it is truly unused (not data read by index) → `FREE_SPACE`.
- [x] Install static CRAM load (`asm.cram_loader`) so the CGB-flagged ROM is no longer blank. Pass `scripts/launch_gate.py`.

## 2. Scene awareness
- [ ] Scene/state variable(s): title, character select (Mage/Bard/Knight/Ranger), overworld, towns/castle, each of the 8 dungeons, 2-player mode, ending → `SCENE_STATE_ADDR`.
- [x] VBlank ISR entry and timing budget → `VBLANK_HOOK`.
- [x] Does the game use DMG palette fades (BGP/OBP writes) for transitions? Those must be mirrored into CRAM.

## 3. BG attributes
- [x] Map/tile pipeline: where map tiles are written to the BG tilemap(s) (0x9800/0x9C00), scroll handling, window layer usage (status bar/text boxes) → `TILEMAP_WRITER_HOOKS`.
- [ ] Tile set per scene → `palettes/bg_tile_categories.yaml`.

## 4. Sprites
- [x] Shadow OAM buffer and HRAM DMA routine → `SHADOW_OAM`, `OAM_DMA_HRAM`.
- [x] Sprite tile ranges for player characters, enemies, projectiles, items.
- [x] Does the game use OAM priority / DMG OBP1? (OAM attr bit 4 has no meaning on CGB; bits 0–2 select CGB palette.)

## 5. Verification harness (port from penta-dragon-dx as needed)
- [ ] Deterministic double build + receipt.
- [ ] OG-vs-DX speed parity on main-loop counters.
- [ ] Per-scene capture gates (mGBA authoritative).

## Open (after run 2)
- [x] Cavern of Hatred (areas $18-$1A) themed (`cavern`), see dungeons.md.
- [ ] Remaining 7 dungeons: find entrances/area ids, add themes (lava/ice...). Max 3 themes besides theme 0 (grow BG_THEMES if needed).
- [ ] Decode the per-area header in bank 4 (graphics list + compressed map) to enumerate all area ids statically.
- [x] Classify $0AEB (rune text) and $14FF (2-player wait): dialog sites (ending.md). 1:$4126, 1:$54E9 still assumed map (2-player only).
- [x] Per-sprite-id palette tuning: monster templates decoded, one colour per type, variant tiers by template (monsters.md).
- [ ] Tier-0 `$32` worm (B21, Hatred `$24`) not seen in an emulator capture (area does not teleport).
- [x] Floor pickups coloured by item type (FloorItems, monsters.md).
- [x] HUD/side panel (hearts, stars, coin, A/B icons) and start menu colored, see menu.md.
- [ ] Side-panel A/B icons on theme-0 maps sit on a tinted square (item palette colour 0). Gold digits: now bright gold on map screens (VRAM bank 1 redraw); the coin icon and the digits on dialog/menu screens keep their colours.
- [x] Observe 0:`$14FF` (2-player "Please wait", forced via 0:`$14BD`): dialog colours.
- [ ] Real hardware test; IPS RLE.
- [x] Dungeon entrance title card + cutscene colored (entrance theme, picture LUT), see cutscene.md.
- [x] Classify LCDC `$87` sites 7:`$40BF` (rune shrine), 7:`$4AE3` (ending throne room): scene themes + LUTs (ending.md).
- [ ] 2-player-only screens 3:`$6F78/$6FAC/$71FF/$720E`, 3:`$79FC/$7A21` keep the default text colours (not reachable without a link partner).
- [ ] Hero in the cutscene uses the gameplay avatar palette (navy/skin/white); a cutscene-only OBJ palette would need OBJ themes.
- [x] Per-dungeon title-card tints (CARD_TINT by HRAM `$FF8F`).
