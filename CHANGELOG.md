# Changelog

## [Unreleased]

### Added (start menu + side panel, 2026-09-26)

- Start menu (0:`$10A8`) has its own LCD mode and `menu` theme: paper background, gold-brown
  frames, skin-toned portrait, gold digits, red/orange cursor, and every item icon coloured by
  item id (`item_palettes`: wood bows, steel swords/armour, gold coins/keys, red potions/hearts,
  blue/green runes...).
- Side panel (A/B items, gold, hearts, stars) coloured on the map, in dialogs and in the menu:
  cream/parchment panel (dusty in the cavern), gold coin, stars and letters, red hearts, A/B icons
  in their inventory colours. It is the window layer on the map, so scrolling does not disturb it.
- Live refresh: equipping inside the menu recolours the A/B icons and the swapped slot at once
  (hook at the end of `$04C1`), plus a rotating per-frame refresh.
- `scripts/capture_menu.py`: `artifacts/menu_compare.png`, `artifacts/side_panel_compare.png`,
  `save_states/{og,dx}_menu.state`. Notes: `menu.md`.

### Fixed (menu run)

- The start menu was treated as a map screen (random coloured blocks); dialogs now use the UI
  theme and closing the menu/dialog restores the area theme.

### Added (dungeon entrance cutscene, 2026-09-26)

- Dungeon title card (bank 7 `$4619`) in its own `entrance` theme: navy card,
  gold letters, gold HUD.
- Entrance cutscene (bank 7 `$4692`: cliff, cave mouth, mountains, plain, the
  champion walking into the cave) colored with its own tile->palette LUT
  (`pictures.entrance`, bank 8 `$5600`) plus per-cell fixups (`$5700`): brown
  cliff, violet mountains, misty green plain, ochre ground, banded dusk sky.
  Picture palettes share colours 2-3 so region boundaries have no seams.
- Blank transition screens (bank 7 `$438B`) and flat DMG palettes
  (`BGP=$00/$FF`) render one uniform `flat_bg` colour: no mosaic of palette
  colour 0 before the title card.
- `scripts/capture_entry_sequence.py`: frame-by-frame recordings of the
  entrance (GIFs, strips, cutscene/title-card comparisons), exit and ladder
  transitions in `artifacts/`. Notes: `cutscene.md`.

### Fixed

- The cutscene hero was drawn black: OBP0 `$34` shows shade 0 on the hero;
  OBJ palettes' colour 0 is now white as on DMG.
- `capture_screens.py`: the original's run now reaches cavern level 3 (more
  retries per step while a monster blocks the way); new `cavern_approach` scene/state.

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
