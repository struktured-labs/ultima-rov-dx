# Dungeons

Evidence: PyBoy runs of the original ROM (DMG) and the DX build (CGB) scripted
by `scripts/capture_screens.py` (cell-accurate navigation via `$FF91`), RAM
dumps of `$C600-$C6FF`, `$FFA0-$FFAF` and `$C580-$C58F`.

## Cavern of Hatred: how to get there
From the overworld start (south of Lord British's castle, overworld cell `$96`):
right 1, up 2, left 1, up 1-2 cells. The castle blocks the direct path; the
cave mouth (graphic in the mountains) is due north of the castle. A title card
"The Cavern of Hatred" shows, then area `$18` loads with the player on the
up-ladder (cell `$66`). mGBA: same keys in real time reach it (see
`artifacts/mgba/mgba_cavern_level1.png`).

## Map representation (all areas)
* Each area is one 16x16-cell map (256x256 px) held at `$C600-$C6FF`, row-major.
  The BG map `$9800` holds the whole area; the camera is SCX/SCY.
* Cell byte: bits 0-5 = metatile graphic g (the same g as the slot loader), bits 6-7 = flags
  (e.g. `$75` = g `$35` + `$40`, `$80-$82` hidden/special cells).
* `$FF91` = player cell (high nibble row, low nibble column).
* The 16 graphics of an area are loaded into the metatile slots on entry; they do
  not change while inside the area. Area `$18`'s list is stored at bank 4 `$4CC8`.
* Area changes go through a transient `$D12F` value (`$D6` seen for a frame).

## Cavern of Hatred areas
| Area | Graphics (slot order) | Notes |
|---|---|---|
| `$18` | `00 01 12 04 06 09 0C 13 14 17 18 19 1B 2D 2E 02` | brigand hideout: floor 00, cobble 01, barrels 12, ladders 04 (down, cell `$9E`) / 06 (up), chest 09, tables/beds/chairs 0C 13 17 18 19 2E, door 14, plant 1B, crate 2D, cave mouth 02 |
| `$19` | `01 00 27 02 06 0F 14 23 25 26 28 32 35 2D 2E 02` | arrow floors 25-28 (push the player), fountains 0F, pebbles 23, mushroom 32, void 35; exit to `$1A` at cell `$FD` |
| `$1A` | `00 01 14 02 03 09 0C 0F 18 37 3E 3F 02 2D 2E 02` | grid of rooms behind doors; shrine/altar 3E 37 3F in the north-west room (door at `$C6` did not open westwards: locked or puzzle) |

Monsters (sprite ids at `$C580`): `$0A` bat, `$14` rat, `$1A` skeleton (large, `$9A`),
`$40` gremlin/imp, `$46` hooded rogue.

Floor pickups (heart seen in `$19`) are drawn with BG tiles `$40-$4F`, not sprites;
the status bar uses `$E4-$FF` in the window (`$9C00`).

## All dungeons: area mapping

Method: PyBoy runs of the original ROM (scripts in `tmp/dprobe/`, not committed).
From the overworld, the warp list of the current area (RAM `$C560`, 16 pairs of
cell, destination area, loaded with the area alongside its bank 4 data) was poked
to send the player to each area id, and every reached area's warps were walked
breadth-first. Each dungeon entrance was identified from the title-card table
at bank 1 `$6888` (pairs `area | flag << 7`, cell; index = dungeon 0-8, names
at bank 7 `$7C24`, "The Great Stygian Abyss" at `$7C89`).

**`$D13E` is a second area set.** Bank 1 `$6878`/`$6880` hold (area, cell) pairs
that set it to 1 when you step on them, `(05,5D) (04,51) (04,ED) (04,4F)`, and
pairs that set it to 0, `(00,5D) (14,51) (29,ED) (46,40)`.
With `$D13E` = 1 the same area ids name different maps, so a theme has to be
chosen from the pair (`$D13E`, `$D12F`). The surface-atlas list used by the slot loader
(bank 1 `$4F1C`) also depends on the flag: `$7E8B` `00 02 03 04 05 32 33 4E 51`
(flag 0), `$7E98` `45 46` (flag 1: the Abyss isle), `$7E95` `03 4C` (two-player
mode `$C511`).

| # | Dungeon | Entrance (area/cell) | Areas (`*` = `$D13E` = 1) |
|---|---|---|---|
| 1 | The Cavern of Hatred | `02/66` | `18 19 1A 1B 1C 23 24 25 26 27 28` (and `22`, an unreached copy of `23`) |
| 2 | The Cavern of Deceit | `02/19` | `12-17 2A-2F` |
| 3 | The Cavern of Cowardice | `03/8B` | `06-11` |
| 4 | The Cavern of Injustice | `05/5D` | `00*-13*` (`08*` links to `04*`/`0A*` but was not reached by walking) |
| 5 | The Cavern of Dishonor | `04/51` | `14*-28*` |
| 6 | The Cavern of Selfishness | `03/3B` | `34-4D` (includes `45 46 4C` with flag 0) |
| 7 | The Cavern of Pride | `04/ED`, and the Abyss isle `46*/E1` | `29*-43*` |
| 8 | The Great Stygian Abyss | Abyss isle `46*/2B` | `47*-65*`, plus `44*` (one room off the isle) |

`46*` is the Abyss isle and `45*` its shop, both drawn from the surface atlas. Castles, shops,
side caves and the other places are in `areas.md`. Only unused ids fall back to
`dungeon_theme` (Hatred). Teleporting straight into `29*` shows the death
screen (the arrival cell is a hazard); `2D*` and `38*` were used for screenshots.

The themes are in `palettes/bg_tile_categories.yaml` `area_themes` (`areas` for
flag 0, `areas_alt` for flag 1) and their colors are in `palettes/rov_palettes.yaml`
`bg_themes`/`obj_themes`.
