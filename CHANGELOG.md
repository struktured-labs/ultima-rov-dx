# Changelog

## [Unreleased]

### Added (dungeon colors, 2026-09-26 run 3)

- Per-area themes: `area_themes` in `bg_tile_categories.yaml` + `bg_themes` in
  `rov_palettes.yaml`; runtime swaps BG base colours and metatile palettes by
  area id `$D12F`. First theme `cavern` for the Cavern of Hatred (areas
  `$18-$1A`): dusty floor shared by all palettes, slate cobbles, wood
  furniture/doors, gold arrow floors, blue fountains.
- Map vs text screen modes for game LCD-on sites (mode byte after `rst $28`):
  story/champion/dialog/game-over screens use the UI palette only; floor
  pickups (tiles `$40-$4F`) are red on the map.
- Dungeon monster palettes: bat/skeleton undead, rat folk, gremlin fiend.
- `capture_screens.py`: cell-accurate navigation (`$FF91`), START-until-
  champion-screen sync so DMG and DX runs pick the same champion, second route
  into the Cavern of Hatred, dialog scenes, save states in `save_states/`.
- Notes: `dungeons.md`; area map buffer `$C600`, player cell `$FF91`.

### Added (first color milestone, 2026-09-26)

- `sm83asm`: pure-Python two-pass SM83 assembler (validated against ~95k
  disassembled instructions) used to build the DX runtime from
  `src/ultima_rov_dx/asm/dx.asm`.
- DX runtime + `dx_patch.build`: ROM expanded to 256 KiB (MBC2 max, banks
  8-15 free), CGB-compatible header, double-speed boot, CGB palettes from
  YAML with DMG fade mirroring, BG attributes from metatile graphic index
  (tile-program translator, slot/metatile/LCD-on/logo-dissolve hooks),
  OBJ palettes from sprite graphic ids patched after every OAM DMA.
  Every hook verifies its original bytes; DMG hardware still runs the
  original code paths.
- `game_layout.py` filled with verified addresses; RE notes
  (`memory_map.md`, `bg_tiles.md`, `sprites.md`, `colorization_design.md`).
- Palettes YAML (8 BG + 8 OBJ Ultima-themed palettes), metatile/title
  categories (schema v2), new `obj_categories.yaml`.
- `scripts/capture_screens.py`: headless PyBoy DMG-vs-DX screenshots and
  contact sheet in `artifacts/` (gitignored, generated).

### Changed

- `scripts/build_dx.py` now produces `rom/working/ultima_rov_dx.gbc` and
  `rom/ultima_rov_dx.ips`; launchers use the `.gbc` name.
- `artifacts/` and `rom/*.ips` are gitignored (derived outputs).

### Added

- Project scaffold modeled on penta-dragon-dx: Python ROM patcher layout,
  palette YAML, ROM identification against No-Intro hashes, IPS tooling,
  mGBA single-flight launcher/guard, agent hook, pre-commit policy, and
  ROM-free unit tests.
- Builder fails closed: exit 66 when `rom/Ultima - Runes of Virtue (USA).gb`
  is missing, 65 on a wrong dump, 78 until game hooks are reverse engineered.
