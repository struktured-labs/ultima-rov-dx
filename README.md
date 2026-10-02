# Ultima: Runes of Virtue DX

A Game Boy Color (DX) colorization of *Ultima: Runes of Virtue* (USA)
(Game Boy; Origin Systems, NA FCI 1992), distributed as a **ROM-free IPS
patch**.

Ultima: Runes of Virtue DX adds scene-aware color while keeping the
original's movement, music, maps, and timing. It is a sister project of
[Penta Dragon DX](https://github.com/struktured-labs/penta-dragon-dx).

The ROM is intentionally not stored in this repository. You must supply your
own dump of the original cartridge.

## Current status

**Beta — work in progress.** The castle, the overworld, and the first dungeon
(the Cavern of Hatred) are colorized, and each of the eight dungeons has its
own color theme. Download the patch from
[Releases](https://github.com/struktured-labs/ultima-rov-dx/releases).

### What is colorized

- Title screen (castle picture and logo), menus, and story/text screens
- Per-area color themes: the overworld and Lord British's castle use the base
  Ultima palettes (grass, water, stone, brick, wood...), and every dungeon
  has its own theme based on its name: dusty Hatred, misty sea-green Deceit,
  sickly-moss Cowardice, prison-steel Injustice, rust-and-blood Dishonor,
  sand-and-gold Selfishness, marble-and-purple Pride, and the ash-and-lava
  Great Stygian Abyss (`palettes/rov_palettes.yaml` `bg_themes`)
- Castles, shops and side caves have their own themes too: Lord British's
  castle wings, Lord Simon's castle, the Lycaeum, Empath Abbey, Gnu Gnu's
  and Utomo's shops, the Cat's Lair, Zoltan's gypsy camp, and the side caves
  (`reverse_engineering/notes/areas.md`)
- Player, monster, and NPC sprites, with the original DMG fades mirrored in
  color
- The Cavern of Hatred (all three levels): cobbled rock, wood furniture and
  doors, gold arrow floors, blue fountains, and colored monsters (bat and
  skeleton undead, rat folk, gremlin fiend)
- The dungeon entrance title card (navy card, gold letters) and the
  full-screen entrance cutscene (brown cliff, violet mountains, misty green
  plain, banded dusk sky)
- The start/item menu, with every item icon colored by type (wood bows, steel
  swords and armour, gold coins and keys, red potions and hearts, blue/green
  runes...)
- The parchment side panel, with red hearts, gold stars, and A/B item icons
  that match their bag colors. Equipping an item updates the icons right away.

### Known gaps

- Dungeons 2-8 have their own themes, but only their tile palettes and the
  black-knight palette were tuned; monster colors and the per-graphic palette
  choices still come from the Cavern of Hatred. Their title cards reuse the
  navy/gold entrance card.
- Floor pickups (map tiles `$40-$4F`) all share the heart's red palette.
- The gold amount in the side panel is drawn in dark brown, because the
  original uses only its darkest shade.
- On the overworld and in the castle, the A/B icons sit on a tinted square.
- Some screens have not been confirmed yet (a few unobserved text and picture
  screens). See
  [`reverse_engineering/notes/TODO.md`](reverse_engineering/notes/TODO.md).

## Apply the patch

1. Get your own dump of the original ROM:

   | Field | Value |
   |---|---|
   | File | `Ultima - Runes of Virtue (USA).gb` |
   | Size | 131072 bytes |
   | MD5 | `411c3d168141d10eddd93243f2a7765f` |
   | SHA-1 | `8d911cbbc6bd1518a85282def7f01d3add16e596` |
   | CRC32 | `c44a0f1e` |

2. Download `ultima_rov_dx.ips` from
   [Releases](https://github.com/struktured-labs/ultima-rov-dx/releases), or
   take the latest build committed at
   [`rom/ultima_rov_dx.ips`](rom/ultima_rov_dx.ips).
3. Apply the patch with [Floating IPS (Flips)](https://github.com/Alcaro/Flips)
   or the in-browser [RomPatcher.js](https://www.marcrobledo.com/RomPatcher.js/).
4. Give the output a `.gbc` extension, for example
   `Ultima - Runes of Virtue DX.gbc`. The patched ROM is 256 KiB. Each release
   lists its expected MD5.

It has been played on the MiSTer GBC core and in PyBoy and mGBA. On original
DMG hardware, the patched ROM still runs the original code paths.

## Build from source

Put your ROM at `rom/Ultima - Runes of Virtue (USA).gb`, or set
`ULTIMA_ROV_ROM=/absolute/path.gb`.

```bash
uv sync                                     # add --extra emu for PyBoy probes/captures
python3 scripts/check_rom.py                # verify the ROM and print its header
uv run python scripts/build_dx.py           # build the patched ROM and the IPS
scripts/launch_mgba.sh rom/working/ultima_rov_dx.gbc   # guarded headed play
```

Outputs:

- `rom/working/ultima_rov_dx.gbc`: the patched ROM (gitignored)
- `rom/ultima_rov_dx.ips`: the ROM-free patch (committed)

The launcher is deliberate: it goes through a project-wide single-flight
lock so emulator processes never pile up (see `AGENTS.md`).

## Colors

Colors are defined in YAML rather than hand-edited ROM bytes:

- `palettes/rov_palettes.yaml`: BG/OBJ CGB palettes, per-area `bg_themes`,
  item palettes
- `palettes/bg_tile_categories.yaml`: metatile → material category, area
  themes, picture LUTs
- `palettes/obj_categories.yaml`: sprite graphic → palette

```bash
uv run rov-dx check-palettes palettes/rov_palettes.yaml
```

## Verification

```bash
uv run python -m unittest discover -s tests -v
python3 scripts/diagnostics/verify_mgba_singleflight_guard.py
scripts/install_git_hooks.sh               # enable .githooks/pre-commit
```

For DMG-vs-DX comparison screenshots, run `scripts/capture_screens.py`,
`scripts/capture_entry_sequence.py`, and `scripts/capture_menu.py`. They write
to `artifacts/`, which is gitignored.

- [Changelog](CHANGELOG.md)
- [Technical documentation index](docs/INDEX.md)
- [Verified ROM facts](docs/rom_facts.md)

## Distribution

This repository contains source code, palette data, verification tools, and
the ROM-free IPS patch (committed at `rom/ultima_rov_dx.ips` and also attached
to GitHub Releases). Neither the repository nor its releases contain the
original or modified game ROM, save files, or emulator states.

*Ultima: Runes of Virtue* is owned by its original rights holders. Ultima:
Runes of Virtue DX is an unofficial fan project.
