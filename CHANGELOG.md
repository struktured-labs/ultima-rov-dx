# Changelog

## [Unreleased]

### Fixed (hardware timing, monster flash, panel icons, 2026-10-03)

- VBlank budget on real hardware: sprite palettes are now computed at the game's idle waits
  (halt wait 0:`$1EE7`, VBlank-flag wait 0:`$02EA`, animated-tile wait 0:`$175A`) into the shadow OAM, so the OAM DMA carries them
  and the VBlank hook no longer overruns. Instrumented SameBoy: blocked VRAM writes 3,184 → 0,
  blocked OAM writes 436 → 36 (2 title frames), palette writes 0 (`reverse_engineering/notes/hardware_timing.md`).
  This fixes torn animated tiles (the game's 0:`$176A` copy) and one-frame wrong sprite palettes.
- Strong monsters no longer flash the base (green) palette for a frame when they spawn or change
  sprite slot: tiers are rebuilt from the records right before the DMA (0 wrong frames in 6,400).
- A/B icons no longer sit on a tinted square: new `overworld` BG theme (areas 00, 02-05, 46 alt)
  with parchment colour 0 for stone/wood/earth/fire; Lycaeum grounds, market and Simon's shop
  aligned; water/grass item icons fall back to the panel palette on surface maps (`IconPal`).
  Food and rocks now use `wood` instead of `earth`.
- Start menu: the portrait (BG palette 5, `earth`, now unused by items) takes the current
  champion's colours (Mariah violet, Iolo green, Dupre red, Shamino leather).
- Side-panel live refresh gets more VBlank time (1,519 → 2,260 cells per 600 frames).

### Added (tools)

- `tools/sameboy_harness` + `scripts/hw_access_scan.py`: SameBoy-core write logger for
  VRAM / CGB palette / OAM access while blocked, per speed and PC.

### Changed (monster variants and floor pickups, 2026-10-02)

- Monster templates decoded (`reverse_engineering/notes/monsters.md`). Each monster graphic keeps
  one colour everywhere; variants of the same sprite with more HP/damage use the next tier:
  `monster` green (OBJ 1), `monster_strong` red (OBJ 2), `monster_elite` purple (OBJ 3). Tiers
  come from the template (bank-2 allocator hook, `monsters.py` at build time), never from the area:
  red slimes (48/16 vs 64/8), strong gremlins, 25-damage skeletons, big rock beasts and worms,
  three troll tiers.
- Removed the per-dungeon steel tint of the black knights (`obj_themes`); they are `royal`
  everywhere. Replaced the fiend/beast/undead OBJ palettes. Rat moved to `monster`, imp `$40` and
  `$5E` (talking NPCs only) to `folk`.
- Floor pickups (BG tiles `$40-$7B`) use their item's palette (gold coins/keys/stars, red hearts
  and potions, steel swords/armour, wood bows, blue flasks/staffs, brown food) instead of all red.

### Added (end game and story screens, 2026-10-02)

- The ending, credits, death screen and rune shrine are colorized
  (`reverse_engineering/notes/ending.md`): congratulations text in royal purple on vellum; the
  throne room with stone walls, sky windows, a crimson banner with a gold ankh, a gold throne,
  Lord British in red and carpeted steps; credits in cream on night blue; ledger-green high
  scores; the friends-and-foes parade on pale sky paper with folk-brown sprites; the rune shrine
  in lavender marble with golden light and a red rune; the skull in bone on blood-black with
  white/gold stars.
- Scene mechanism: bank-8 `SceneHook` (via WRAM2 `SceneTramp`) picks a theme, picture LUT and
  OBJ palette 0 per LCD-on site (`bg_tile_categories.yaml scenes`, `rov_palettes.yaml scene_obj`).
- The rune text (0:`$0AEB`) and the 2-player "Please wait" screen (0:`$14FF`) are dialog sites
  (they showed map colours, with blue blocks behind spaces).
- Dungeon title cards are tinted per dungeon (`rov_palettes.yaml card_tints`); the Cavern of
  Hatred card is unchanged.
- The side-panel gold amount is bright gold with a dark shadow on map screens (digits redrawn
  into VRAM bank 1).
- Not handled: 2-player-only screens (game over, score, link "Please wait"), which keep the
  default text colours.

### Added (champion colours, 2026-10-02)

- Each champion has its own sprite colours, picked from `$D133` (0 Mariah, 1 Iolo, 2 Dupre,
  3 Shamino; `reverse_engineering/notes/heroes.md`): Mariah in violet robes, Iolo in forest
  green, Dupre in steel armour with red trim, Shamino in a dark green cloak with leather brown.
  Walking, the attack pose and weapon, and the entrance-cutscene champion all follow; monsters
  and NPCs are unchanged.
- The champion-select portraits each get their own palette (BG palettes 1-4) to match.
- `rov_palettes.yaml` `heroes`; bank 8 `HERO_OBJ_ROM`, WRAM2 `HERO_CACHED`/`HERO_BG`.
- Not handled: the 2-player (link cable) partner sprite.

### Added (themes for castles, shops and side caves, 2026-10-02)

- Every valid area outside the dungeons was identified from NPC dialog and warps
  (`reverse_engineering/notes/areas.md`). Each now has a theme instead of the Hatred fallback:
  `castle` (Lord British's castle wings), `simon` (Lord Simon's castle), `lycaeum_grounds` /
  `lycaeum`, `town` (Gnu Gnu's shops, Utomo's armoury), `market` (Gnu Gnu's stall, the Isle of the
  Avatar shop), `catslair`, `sidecave` (spider-web cave, Loubet's cave), `abbey` (Empath Abbey),
  `gypsy` (Zoltan's camp). Lord British's throne room, the overworld and the dungeons are unchanged.
- Theme table 16 -> 32 ROM themes; themes share up to 16 metatile palette maps through `MP_IDX`.
  `surface: true` lets a theme claim surface-atlas areas.
- Area `08*` mapped to Injustice; `22` (unreached copy of Hatred `23`) to Hatred.

### Added (per-dungeon themes, 2026-10-02)

- Each of the eight dungeons has its own color theme; the areas of each one were decoded from
  the warp lists (`reverse_engineering/notes/dungeons.md`). Themes are picked by the area id
  `$D12F` and the second-area-set flag `$D13E`, so Injustice, Dishonor, Pride and the Abyss
  (which reuse area ids) are mapped correctly. Hatred looks unchanged.
- Theme table expanded from 4 to 16 ROM themes: colors live in bank 8 (`THEME_BG_ROM`,
  `THEME_OBJ_ROM`, `METAPAL` 16x128, `AREA_THEME` 512) and the active dungeon theme is copied
  into WRAM slot 1 by `MapTheme` when an area loads.
- `surface_areas_alt` (`45 46`, the Abyss isle). Areas `45 46 4C` with `$D13E` = 0 are
  Selfishness levels, not surface areas.

### Fixed (livestream issues #1-#6, PR #7, 2026-09-27)

- #1 Champion select: portraits in skin tones (LCD-on sites bank 3 `$78F8/$7954/$79C7`, mode `$7F`).
- #2 Text screens and dialogs: gold box frames, skin-toned speaker portrait.
- #3 The champion's attack pose keeps the player palette (sprites in slots past the loader count
  `$C539` are not monsters).
- #4 Map attributes are swept (16 cells per VBlank) after metatile slots reload with the LCD on,
  so caves/trees no longer stay blue after a voyage.
- #5 Every dungeon-atlas area (not in `surface_areas`) gets the cavern theme, including Deceit.
- #6 The sailing ship is brown (`ship: folk`).

### Added (PR #7)

- Wand fireballs orange-red; trumpet icon gold; empty hearts/stars grey in every theme; dungeon
  black knights in dark steel (per-theme OBJ palette 5, `obj_themes`).
- Title logo: **STRUKTURED LABS** credit and a DX plate (`palettes/branding.yaml`), both original
  hand-drawn art in `branding.py` (no ROM font data). MAX_THEMES 8 -> 4.

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
