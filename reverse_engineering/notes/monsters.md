# Monsters (templates, variants, colour tiers)

## Templates

Every map object (monster, NPC, missile, chest...) is spawned from a 9-byte
template in bank 1:

* `$55AF + 9*U`. U = list type (`$00-$42`) for the area's first object group,
  and U = 67 + type for the second ("alt") group, which the spawner reads from
  `$580A` (= `$55AF + 9*67`) once the list pointer reaches `[$C508]`.
  67 + 72 = 139 templates. Area list types `$48-$67` are floor items, not
  templates.
* The area object list is at `$C5C0` (pairs: position, type | `$80`).

| byte | meaning |
|---|---|
| 0 | count |
| 1 | graphic: bit 7 = large (24-tile animation range), bit 6 = people bank (bank 1 `$5A92`), else monster bank (bank 6 `$6AD9`); `$C580` stores `gfx & $FE`, so the OBJ palette key is `gfx & $7E` |
| 2 | flags |
| 3 | HP |
| 4 | behaviour / AI |
| 5 | contact damage (`>= $78`: no contact damage / special; `>= $80`: talk id of an NPC) |
| 6-8 | misc (speed, drop...) |

## Records

* 16-byte records at WRAM1 `$D000-$D0FF`. `$FF` in byte 0 means the slot is free.
* Template bytes 2-8 are copied to record bytes 7-13 (record +8 = HP, +10 = damage).
* +2 = OAM tile base ^ (gfx & `$81`).
* +3 = shadow-OAM offset of the record's two 8x16 entries (0 = not drawn).
* Allocator: bank 2 `$5FE6` (`ld bc,$D000`, then scans for `$FF`; returns NZ when full, else BC = record).
  * Spawner: 0:`$2895` (return `$2898`). Stack in the allocator: `[ret][bc][bc][template+1]`.
  * Cloner (objects that copy an existing record): bank 2 `$5B47` (return `$5B4A`). Stack: `[ret][source record]`.

## Variants: the same graphic with different stats

Yes, there are variants. The game reuses one sprite with different HP and
damage, sometimes in the same room. For example, Hatred `$27` has both 24/15
and 24/25 skeletons, and Deceit `$2C` has trolls with 1, 15 and 25 damage.

Data: templates read from the ROM (`src/ultima_rov_dx/monsters.py`); area
placement from teleporting to every area in PyBoy and decoding `$C5C0`.
"other" = castles, side caves and the overworld. Damage `-` = no contact
damage (bosses, NPC-like objects). The tier column is the colour the DX build
gives them.

| graphic | templates | HP | dmg | tier | where |
|---|---|---|---|---|---|
| $00 dragon | A15, B03 | 127 | - | 0 | other (boss) |
| $02 shadow dancer | B0C, B0D | 72 | - | 0 | Cowardice, Hatred, other |
| $02 shadow dancer | A06, A0B, A1A, A26, A28, A35 | 80 | - | 0 | all dungeons |
| $02 shadow dancer | A1F | 99 | - | 0 | Abyss, Dishonor, Hatred, Pride, Selfishness |
| $04 reaper | A09, A0C, B06 | 32 | 8 | 0 | Abyss, Cowardice, Dishonor, Injustice, Pride, Selfishness |
| $06 boss | A32 | 127 | - | 0 | other |
| $0A bat | A01, A27, B00, B1B, B26, B27, B28 | 8 | 8 | 0 | every dungeon |
| $0A bat | A2C, A2D | 80 | - | 0 | (unplaced) |
| $0C slime | A02 | 64 | 8 | 0 | Abyss, Dishonor, Injustice, Pride |
| $0C slime | **B11** | 48 | **16** | **1** | Deceit, Dishonor, Injustice, Selfishness |
| $0E gremlin | A05, A0A, B08 | 16 | 7 | 0 | Abyss, Cowardice, Dishonor, Injustice, Pride, Selfishness |
| $0E gremlin | **A08**, B07 | 64-72 | **23** | **1** | Selfishness (B07 unplaced) |
| $10 sea serpent (missile) | A16, B04 | 1 | 7 | 0 | other |
| $14 rat | A00, A0E, A25, A2F, B0B, B1C | 8 | 8 | 0 | every dungeon |
| $16 spider | A0D, A1B, B13 | 24 | 8 | 0 | Abyss, Pride, Selfishness |
| $1A skeleton | A10, A11, B0E, B0F | 24 | 15 | 0 | most dungeons |
| $1A skeleton | **A21, A40, B10** | 24 | **25** | **1** | Abyss, Hatred, Injustice, Pride, Selfishness |
| $20 rock beast | B09, B22, B24, B25, B2D | 8 | 24 | 0 | Abyss, Pride, Selfishness |
| $20 rock beast | A20 | 80 | - | 0 | other |
| $20 rock beast | **A14** | **72** | 24 | **1** | Abyss, Pride, Selfishness |
| $22 troll | A24 / B1A, B1E / A1E / B1F | 32-64 | 1-2 | 0 | Hatred, Injustice, Deceit, Dishonor, Abyss, Pride |
| $22 troll | **B1D / B17 / A13** | 32-64 | **15-17** | **1** | Deceit, Abyss, Pride, Selfishness |
| $22 troll | **A41, B16 / A12** | 32-64 | **25** | **2** | Abyss, Deceit, Dishonor, Pride, Selfishness, Cowardice |
| $28 shark fin | A38, A39, B01 | 24 | 7 | 0 | Abyss, Dishonor, Pride |
| $2A octopus | A1C, B14 | 72 | 16 | 0 | Abyss, Dishonor, Pride |
| $2C serpent | A04, B12 | 24 | 8 | 0 | Deceit, Dishonor, Selfishness |
| $2C serpent | **A3A** | 40 | **27** | **1** | other |
| $2E hooded mage | A2B | 127 | 19 | 0 | Dishonor (boss) |
| $32 worm | B21 | 8 | 8 | 0 | Hatred |
| $32 worm | **B15** | **72** | 8 | **1** | Abyss, Dishonor, Pride, Selfishness |
| $34 cyclops | A3B, A3C, A42, B02 | 48 | 27 | 0 | Abyss, Pride |
| $3C missile | A33 | 1 | 7 | 0 | other |

Areas where variants share a room or level: Hatred `$27` (skeletons),
Deceit `$2C` and Pride/Abyss `$3D*` (all three troll tiers), Selfishness `$4A`
(both gremlins). So the area can't decide the colour. The template has to.

People-bank graphics are not tiered. `$64` brigands have 32/7 and 40/7, the
same tier under the rule, so they stay `folk`. `$40` and `$5E` are only used
by talking NPCs (damage byte `>= $80`), so they are `folk` too. Monster
graphics `$1C $1E $24 $26 $36 $38` and people `$72 $74` have no template;
they stay in the `monster` list so they get one stable colour if they ever show up.

### Tier rule (`monsters.tiers`)

The rule runs per graphic in the `monster` category, over hostile templates
only (damage < `$78`, HP > 1):

1. Sort the distinct (damage, HP) pairs.
2. A new tier starts when damage is ≥ 1.4x the current tier's base and at
   least 4 more, or when HP is ≥ 4x the base.
3. At most 3 tiers. Non-hostile templates (bosses, missiles, talkers) are tier 0.

The rule is computed from the ROM at build time. It is packed as one nibble
per template (70 bytes) at bank 2 `$7FBA` (`TIER_TAB`).

## Colours

The convention (Carmelo, 2026-10-10): each creature has its natural colour everywhere; a
different colour only marks a tougher version of the same sprite, never a different dungeon.
The table is `rov_palettes.yaml` `creatures` (one entry per creature: sprite keys, colours,
reason, and `variants` keyed by the template tiers). Folk, royals, items and the player keep
their fixed categories (`obj_categories.yaml`); the wizard `$64` is a creature now.

Tiered creatures (variant colours): slime, gremlin, skeleton, jagger, troll (2 variants),
snake, centipede. Only templates observed in the ROM with higher HP/damage on the same
graphic get a variant (tier rule below).

| OBJ palette | use |
|---|---|
| 0 | avatar / player (champion colours rewritten per hero) |
| 1-6 | assigned per area to the creature/folk/royal/item classes present (below) |
| 7 | `obp1` — cursor, wand fire, hit flash (DMG OBP1 sprites) |

### Per-area allocation (`creatures.py`, bank-9 `NatLcd9` / `NatPrep9`)

* At map LCD-on, the classes of the loaded sprite slots (`$C580`, `[$C539]`) and the area's
  spawn list get palettes 1-6; a tiered class gets a contiguous block (base + variants) and
  `OBJPAL[key]` = first palette | `$80`, so `TierPal` adds `ENTRY_TIER`.
* `Prep8` calls `NatPrep9` every frame: a signature of the slots is compared and the
  allocation redone only on a change, only below LY 96 (`NAT_LY`) or in VBlank (else retried
  next frame). Changed palettes set `NAT_DIRTY` bits; `SyncDirty8` (after the OAM DMA)
  writes them to CRAM while LY is 144-145 (144-147 in the parade).
* Overflow (more than 6 palettes wanted): variant blocks shrink to the base colour first; only
  then would a class share its nearest-colour class's palette. Observed: Injustice `00*`
  (slime), Selfishness `4C` (centipede, troll, skeleton), Pride/Abyss `2B*` (jagger), `38*`
  (troll); no class sharing anywhere.
* The black-knight borrow and per-area `obj_themes` are gone (the builder rejects
  `tier_palettes`, `knight_borrow`, `obj_themes`).

### Parade

The builder plans the attract parade per page (`creatures.parade_plan`): each page's classes
get palettes disjoint from the previous page's (0 and 7 allowed, CRAM only). Page 0 is set at
the parade LCD-on (`ParadePage9`); while page k shows, `ParadeStep9` (from `SyncDirty8`,
VBlank) writes page k+1's palettes one per frame (`PARADE_STEP`/`PARADE_TGT`), so the page
switch itself does no palette work (no colour work runs during the page reload).

### Runtime

* The bank-2 `AllocHook` (`$7F34`, replacing `ld bc,$D000` at `$5FE6`) runs the
  original allocator. On success on CGB, it reads the caller from the stack:
  * spawner (`$2898`): template pointer → U → `TIER_TAB` nibble.
  * cloner (`$5B4A`): copy the source record's tier.

  It stores the result in `REC_TIER[record >> 4]` (WRAM2 `$D7C0`, 16 bytes).
* Sprite palettes are computed at the game's idle waits, outside VBlank, by bank-8 `Prep8`
  (via ROM0 `PrepTramp` in interrupt-vector padding and WRAM2 `W2Prep`). Those waits are the
  main loop's halt wait 0:`$1EE7`, the VBlank-flag wait 0:`$02EA` and the animated-tile copy's
  wait 0:`$175A` (not the routine 0:`$02DC` itself, see hardware_timing.md).
  The shadow OAM is final there. `Prep8` clears the palette bits of all 40 shadow entries. In
  map mode it rebuilds `ENTRY_TIER` (WRAM2 `$DB10`, 40 bytes) from every live record's
  shadow-OAM offset (+3) with all entries known (`TierCore`, C = `$80`), and runs `LiveFloor`.
  Then it runs `OamPass` over `$C000`, writing each entry's palette into the shadow attribute
  byte, so the OAM DMA itself carries the colours. It sets `PREP_DONE` (`$D7DF`).
* When the palette pass picks palette 1 (`monster`), `TierPal` adds `ENTRY_TIER[entry]`,
  giving 1/2/3. The tiers come from the same shadow OAM that is about to be DMA'd, so no frame
  shows a monster in the base colour when it spawns or changes sprite slot (the old post-DMA
  scan lagged one frame: 2 of 722 entries in Selfishness `$4A`). Now 0 of about 6,400
  monster-frames are wrong over 4A/2C/27/49/4C/3D.
* After a DMA with `PREP_DONE` set, the hook skips its OAM pass. Without prep (the wait came at
  LY 128-145, too close to VBlank), the hook runs `OamPass` over `$FE00`. It keeps entries
  whose palette bits are already set (carried from an earlier prep) and colours the rest, then
  runs the old tier scan (`W2AfterDmaT`). An entry that is still unknown is rebuilt on demand
  (`TierPal` → `TierFar` C = `$80`).
* Why: the post-DMA OAM pass, live refresh and tier scan took about 8,000 T-cycles inside the
  VBlank interrupt (VBlank is 4,560), so the game's own VBlank VRAM work after the DMA (the
  animated-tile copy at 0:`$176A`) spilled into mode 3. See `hardware_timing.md`.
* The side-panel live refresh (`HELPER` reads, `HudItemsLut`, 4 `HudCellLy` cells) runs only
  when the hook starts by LY 145. On a late DMA (0:`$1717` at LY 145) the game's tile copy needs
  that time. `HudCellLy` stops when LY leaves VBlank, so its VRAM writes are never lost.

## Floor pickups

* Floor items are in `$C5B0+k` (k = 0-14, `$FF` = empty), filled by the area loader
  (0:`$2721`) and drops (0:`$1450`/`$145E`).
* Item k is drawn with BG tiles `$40+4k..$43+4k`, a copy of its inventory icon.
  The original DX build gave `$40-$4F` the red `fire` palette and the rest the
  UI palette.
* Now, `FloorItems` (WRAM2 section `wram2c`, `$DB40`) re-colours those four
  tiles with the item's own `item_palettes` entry whenever `$C5B0+k` changes
  (cache `ITEM_CACHE`, WRAM2 `$D7D0`). The menu icons use the same palette, so:
  * coins, keys, stars, lamp: gold
  * hearts, red potions, runes: fire
  * swords, armour, hammer: stone
  * bows, crossbow, boots: wood
  * flasks, staffs: water
  * food: earth

  These are BG palettes, so the OBJ budget is unchanged.
