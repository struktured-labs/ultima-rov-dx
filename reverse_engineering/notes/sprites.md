# Sprites

* Shadow OAM at `$C000`, DMA via `$FF80` (see memory_map.md).
* Loader `$28E1`: sprite slot b -> tiles `$80+b*8` (VRAM `$8800+b*$80`).
  Graphic id in `$C580+b`: bit7 = large (uses the next slots, which hold `$FF`),
  bit6 = people (bank1 `$5A92`), else monsters (bank6 `$6AD9`); 128 bytes per graphic.
* OAM tiles below `$80` are the player character (and player projectiles/effects).
* DMG OAM bit 4 (OBP1) is used on the title screen.

Known ids (from sprite sheet dumps; palette choice in `palettes/obj_categories.yaml`):
`$70` jester (folk), `$46` hooded rogue (folk), Lord British (royal). Monster graphics are all in
the `monster` category and are coloured by variant tier (green / red / purple), see monsters.md for
templates, stats and the tier rule.
