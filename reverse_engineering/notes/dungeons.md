# Dungeons: Cavern of Hatred (first dungeon)

Evidence: PyBoy runs of the original ROM (DMG) and the DX build (CGB) scripted
by `scripts/capture_screens.py` (cell-accurate navigation via `$FF91`), RAM
dumps of `$C600-$C6FF`, `$FFA0-$FFAF` and `$C580-$C58F`.

## How to get there
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

## Other dungeons
Not visited yet. Lord British sends the player to the Cavern of Hatred first
("due north of here"); other entrances are elsewhere on the overworld.
