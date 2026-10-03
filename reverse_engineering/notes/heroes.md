# Champions (playable characters)

The champion select screen (bank 3, LCD-on `$78F8/$7954/$79C7`, DX mode byte `$7F`) offers four
champions, left to right:

| `$D133` | Champion | Home / text on the select screen | Starting weapon (A item `$D126`) |
|---|---|---|---|
| 0 | Mariah the Mage | Moonglow; "begins with but a dagger, can best wield the powerful magic weapons" | dagger |
| 1 | Iolo the Bard | Britain; long bow | long bow |
| 2 | Dupre | Jhelom, best swordsman; the only one who starts with armour | sword |
| 3 | Shamino the Ranger | Trinsic; "well balanced fighter", magic throwing axe | magic throwing axe |

## RAM

- **WRAM1 `$D133` = champion** (0-3, table above). On the select screen it is also the cursor:
  Right / A step it, Start confirms; it starts on Shamino (3). Stats follow at `$D121-$D123`;
  `$D125` B item (Mariah gets `$34`, bank 3 `$75E8`/`$7869`), `$D126` A item.
- 2-player (link cable): the partner's copy of the `$D100` block sits at `$D140-$D17F`; **partner
  champion = `$D173`**. Bank 3 `$6F19` copies `$D100-` to `$D800-` for the link exchange. `$C511` is
  the overworld/2-player flag (see memory_map.md).

## Sprite graphics

- Player tiles are OBJ tiles `< $80` (VRAM `$8000-`). Bank 3 `$6FC7` loads them from
  `HL = $4300 + $D133 * $180`; bank 0 `$1957` offsets other champion graphics by `$D133 * $C0`.
- Attack pose: the body becomes OBJ tiles `$E0/$E2` (at the player's position) plus the weapon in
  tiles `$10/$12` or `$14/$16` (by facing) beside it, all with OBJ palette 0.
- Entrance cutscene (bank 7 `$4056`): the walking champion is `DE = $7740 + $D133 * $40` copied to
  VRAM `$8C00`, drawn with OBP0 `$34` (CGB: palette 0 with shades 0,1,3,0).
- 2-player partner graphics (`$4300 + $D173 * $180`) go to VRAM `$8C00/$8D80` (sprite slots 8 and
  11, tiles `$C0/$D8`).
- Select screen portraits are BG tiles: Mariah `$10-$1F`, Iolo `$20-$2F`, Dupre `$30-$3F`,
  Shamino `$80-$8F`.

## DX colours

- `palettes/rov_palettes.yaml` `heroes`: per champion, 4 sprite colours and 4 portrait colours.
- Sprite: bank-8 `HeroObj` (called from `Slot`, i.e. on every area load) copies
  `HERO_OBJ_ROM + $D133 * 8` into `BASE_OBJ` palette 0 (`PLAYER_PAL`) when it differs from
  `HERO_CACHED` (WRAM2 `$D717`, `$FF` at boot) and forces an OBJ resync. Walk, attack pose,
  weapon and cutscene champion all use palette 0, so they all follow. Monster/NPC palettes 1-7
  are untouched.
- Portraits: `bg_tile_categories.yaml` `champion_screen` maps the four portrait ranges to BG
  palettes 1-4; on the champion-select LCD-on, `W2LcdOnBody` loads `HERO_BG` (WRAM2 `$DD00`, the
  unused LUT_GAME entries `$00-$1F`) into those palettes and invalidates `CUR_THEME` so the next
  screen reloads its theme.

## Not handled

- 2-player partner: its sprite would need its own OBJ palette (all 8 are in use) and PyBoy has no
  link cable to test it; the partner is drawn with whatever palette its slot uses.
- The start-menu portrait keeps its palette (all menu palettes are taken by the item icons).
- The select-screen highlight frame keeps the default colours.
