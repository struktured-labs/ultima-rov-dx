# Changelog

## [Unreleased]

### Changed (talk-dialog portraits in per-tile colours, 2026-10-11)

- Portraits break the one-palette limit: each of the 16 portrait tiles picks its palette.
  `DlgPortrait8` loads the portrait's base palette into BG palette 5 as before and up to two
  more into UI palettes the dialog screen does not show (grass, water, stone, wood, minus the
  two the side-panel A/B icons use: `PORTRAIT_SLOTS`), and writes the tile palettes into the
  live LUT before the attribute fill. The next screen reloads its theme and LUT, so the
  borrowed palettes come back. Text, frames and side panel are unchanged.
- Human NPCs: face tiles in natural skin (ecffaca), hair / hat / hood / clothes tiles in their
  map hue at ecffaca contrast: Chuckles' jester hat red and green, Melissa's hood rose,
  Penumbra's hair indigo, Taynith's hood forest green, Ariana's hair gold, Zoltan's bandana
  purple, Finn's cap blue, Loubet teal, Johann olive, Utomo saffron (outline only). Royals:
  skin face, gold crown, red robe. Animals, the sign and the Black Knight keep one palette.
- Config: `rov_palettes.yaml` `portrait_palettes` (named, with a `why`; `bold` for the two
  saturated fills, jester red and royal red) and `dialog_portraits` `tiles` / `pals`; the
  builder validates them (2 extra palettes at most, enough free palettes for any A/B icons).
  Bank 8: `PORTRAIT_TAB` entries are now (portrait, base, extra 1, extra 2, tile map),
  `PORTRAIT_POOL` `$7A00` (was the unused THEME_OBJ_ROM), `PORTRAIT_SLOTS` `$7B80`.

### Changed (NPC portraits and sprites at ecffaca contrast, 2026-10-11)

- Every portrait (except the Black Knight's inverted helm) keeps the value contrast of the
  ecffaca portraits: light / mid within 8% of the earth palette's luminance (208 / 123), the
  line shade as dark (<= 34). Character colour is only a hue shift of the mid and line shades;
  human faces stay skin (light `#F6C5A4`, mid a skin shadow tinted toward the character).
  Royal portraits: `#F8CCA0` / `#AC6F44` / dark royal red `#4A0C14`. New test
  `test_portrait_contrast_like_ecffaca`.
- Map sprites of the named NPCs (v4, distinct hues): most NPC sprites draw body and outline
  in colour 3, so colour 3 is the saturated character hue at luminance ~50-80 (dark enough to
  outline on castle, town and dungeon floors) and colour 2 the hood / hair / trim at ~123.
  Hues spread round the wheel: Chuckles red with green trim, Klip/Klop chestnut, Dr Cat
  ginger, Utomo saffron, Johann olive, Taynith forest green, Loubet teal, Finn blue, Penumbra
  indigo, Zoltan purple, Ariana plum (gold hair), Melissa rose; Sherry, Kador, Beh Lem stay
  near-neutral. Portraits keep skin faces and carry the hue in their line (`line:` now takes
  a colour, the map hue at ~27). Tests: same-sprite NPCs and common pairs differ by > 40
  degrees of hue; portrait lines stay in the map body's hue family.

### Changed (named NPCs in their own colours on the map, 2026-10-11)

- Each named NPC now has its own natural colour on the map, allocated per area like the
  creatures (`rov_palettes.yaml` `npcs`, with a `why` per entry): Chuckles jester green/red,
  Dr Cat orange tabby, Kador white, Sherry mouse brown-grey, Klip and Klop one chestnut horse,
  Beh Lem slate grey, Utomo saffron, Finn sailor blue, Ariana plum, and the NPCs that share a
  graphic by template: Penumbra midnight blue, Taynith forest green, Melissa rose (hooded
  figure `$46`), Johann green, Loubet teal, Zoltan purple (townsman `$6A`). Unnamed townsfolk,
  Lord British, guards and royals keep their shared palettes.
- Allocation: NPCs go after creatures and shared classes; when a room wants more than 6
  palettes, folk is loaded before them and the NPCs that do not fit wear folk brown. A
  shared-graphic NPC whose area lists one named variant only gets that variant's colours in a
  single palette. Overflow: town `$01` (Johann, Loubet brown) and Pride/Abyss `$38` (Dr Cat
  brown).
- Talk-dialog portraits of the named NPCs use exactly their map colours (`npc:`); royal
  portraits (Lord British, Gnu Gnu, Eep Eep) have a skin-tone face with royal red only in the
  outline / crown shade instead of a red face with a navy outline.
- Parade: the two friends pages show the NPC colours (page 2 preloads 3 palettes).
- Runtime: bank 9 `NAT_NPC` (`$7A00`), WRAM3 scratch `NAT_TM` (`$D1C0`), `NAT_NPCS`
  (`$D200`); `TIER_TAB` also carries the NPC template tiers. Worst-case allocation
  ~+1% vs HEAD on the same scenes (the NEED/PH/SZ clear is unrolled).
- SameBoy vs ecffaca: blocked writes unchanged (OAM 24, pre-existing parade; VRAM/BGPD/OBPD 0);
  re-colour stress in towns `$01`/`$55`: OCPD writes all at LY 146 (VBlank), 0 blocked, Prep8
  ends by LY 79 (HEAD 74); parade OCPD writes LY 147-150, 0 blocked.

### Changed (talk-dialog portraits in their speakers' colours, 2026-10-11)

- Every talk-dialog portrait now takes the colours of the speaker's map sprite instead of the
  shared `earth` skin tones (named NPCs: their map colours, royals softened, see above), signs pale gold like the map sign, and the Black Knight a near-black helm
  (dark steel plates, grey trim, black outline) like his sprite. `rov_palettes.yaml`
  `dialog_portraits`, keyed by the portrait byte of the speaker's text record (`sprite` = map
  graphic whose colours are used, or explicit `colors`).
- Runtime: bank-8 `DlgPortrait8` (from `SceneHook`, LCD off) reads the portrait byte the game
  keeps on its stack at the dialog LCD-on 0:`$1323` and loads BG palette 5 from `PORTRAIT_TAB`
  (bank 8 `$7F00`); text, frame and side panel unchanged. SameBoy: no new blocked writes.

### Changed (natural creature colours, 2026-10-10)

- Monsters use one natural colour per creature everywhere (`rov_palettes.yaml` `creatures`:
  rats brown, slimes green, skeletons bone, trolls mossy green-grey, ...). A different shade
  marks only a tougher version of the same sprite (slime, gremlin, skeleton, jagger, troll,
  snake, centipede). Replaces the green/red/purple tier palettes, the per-area knight theme and
  the Black Knight palette borrow.
- OBJ palettes 1-6 are allocated per area to the classes present and re-allocated when the
  loaded sprites change (outside VBlank, CRAM writes in VBlank only). In the 4 areas that want
  more than 6 palettes the variants fall back to the base colour.
- The attract parade preloads each foe page's colours during the previous page.
- SameBoy: OAM blocked writes 24 (HEAD 25, pre-existing parade OamPass), OBPD 0 blocked.

### Changed (Black Knight near-black via palette borrow, issue #10, prototype 2026-10-08)

- The Black Knight (`$52`) borrows the `royal` OBJ palette 5 while he is loaded and no other
  royal sprite (Lord British, guards, `$50`) is drawn; the runtime rewrites that palette with
  `knight_colors` (near-`black` by default; `steel` and the `black_helm` experiment available) and puts the royal colours back as
  soon as a royal sprite is drawn and on every non-map screen. Tier-2 trolls keep the elite
  purple; the purple stays the knight's fallback. One CRAM palette write (8 bytes) in VBlank,
  only on a change made with the LCD on (`KnightScan8` / `KnightSet8` / `KnightSync8`).

### Fixed (Black Knight colour, issue #10, 2026-10-08)

- The Black Knight (sprite `$52`) no longer uses the `royal` OBJ palette meant for Lord British,
  which drew his grey armour red. He uses the dark `monster_elite` purple everywhere (overworld
  and dungeons); no OBJ palette is free for a separate steel colour.

### Fixed (attract-mode parade, 2026-10-08)

- The "YOUR FRIENDS / YOUR FOES" parade of the title/attract loop now colours each sprite like
  in gameplay: foes in the monster palette (base tier, green), Lord British and Gnu Gnu royal,
  the wisp gold, townsfolk folk. It used OBJ palette 0 for everything after power-on, and the
  last area's sprite-slot palettes after a game. Bank-7 hook on the parade's graphics loader
  (`ParadeLoad`, 7:`$7FF8`), table `PARADE_PAL_ROM` built from OBJPAL
  (`reverse_engineering/notes/ending.md`).

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
