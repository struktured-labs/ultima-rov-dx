# Areas outside the eight dungeons

Every area is named by the pair (`$D13E`, `$D12F`), as described in `dungeons.md`.
Valid ids are `$00-$55` with `$D13E` = 0 and `$00-$65` with `$D13E` = 1. Above those,
the area loader reads text bytes as map data (checked by poking each id in PyBoy;
`$66*-$6E*` repeat `$65*`). Every valid id is listed here or in `dungeons.md`.

## Method
- **Probes:** PyBoy scripts on the original ROM, in `tmp/dprobe/`, not committed.
- **Warps:** each area was reached by poking the warp list at `$C560`, then its own warps were dumped.
  Interiors were then re-entered through their parent's real warp, so the player spawns on the
  right cell.
- **Identification:** a random walk in each area triggered NPC dialog (hook on the dialog box at
  0:`$1323`, text read from `$C000`). Each place below is named from the game's own text. The
  quotes are the ones the NPCs said in that area.
- **Unmatched speakers:** several NPC records in the bank 4 `$6A03` text table (Sherry, Kador,
  Klip/Klop, Ariana...) belong to dungeon levels and are not listed.

## Surface-atlas areas (slot loader list bank 1 `$7E8B`, and `$7E98` under `$D13E` = 1)
| Area | Entrance | Place | Evidence | Theme |
|---|---|---|---|---|
| `00` | `02/86` | Lord British's castle, throne room | Lord British: "Seek thou the Rune of Compassion..."; Chuckles: "Don't listen to stuffy old Lord British" | 0 (base, unchanged) |
| `02 03 04 05` | | the overworld (four quarters) | | 0 |
| `33` | `04/16` | Lord Simon's castle | Honest Finn: "Until Lord Simon returns, I'm king of this castle!"; Johann: "A tunnel beneath the sea leads to the Isle of the Avatar" | `simon` |
| `32` | (no warp leads here) | copy of `33` (same NPCs) | | `simon` |
| `4E` | `02/89` | Gnu Gnu's market stall | Gnu Gnu: "Check out all the nifty stuff I'm selling! I'm saving up for a pet dragon!" | `market` |
| `51` | `03/23` | the Lycaeum, on its island | Penumbra: "Welcome to the Lycaeum. Beware of the Gremlins in the Cavern of Cowardice" | `lycaeum_grounds` |
| `45*` | `46*/CB` | Isle of the Avatar shop (potions, food) | "Beneath the northernmost volcano lies the Abyss." | `market` |
| `46*` | `04/4F` | Isle of the Avatar (the Abyss isle) | | 0 |

## Interiors and side caves (dungeon atlas)
| Area | Entrance | Place | Evidence | Theme |
|---|---|---|---|---|
| `30` | `00/43` | Lord British's castle, west wing (bedrooms, barrels) | | `castle` |
| `31` | `00/C3` | Lord British's castle, east wing (hearts and star on display) | | `castle` |
| `1D` | `02/A5` | Gnu Gnu's first shop | Gnu Gnu: "I'll race you to my other shop!" | `town` |
| `4F` | `4E/17` | Gnu Gnu's back room (items for 7 coins) | | `town` |
| `20` | `04/25` | Utomo's armoury | "Utomo make good weapons, good armor. You buy, then Utomo go buy pineapple!" | `town` |
| `1E` | `03/E8` | the Cat's Lair (shop and tavern) | "Welcome to the Cat's Lair! You can use cheese to lure monsters" | `catslair` |
| `50` | `1E/37` | the Cat's Lair cellar (well, barrels) | | `catslair` |
| `52` | `51/55`, `51/59` | Lycaeum hall | "You should come visit my shop, the Cat's Lair!", "Isn't he a silly kitty?" | `lycaeum` |
| `54` | `51/4A` | Lycaeum puzzle room (arrows, chest) | | `lycaeum` |
| `53` | (no warp leads here) | copy of `54` | | `lycaeum` |
| `55` | `05/33` | Empath Abbey | "Welcome to Empath Abbey! Look for the boomerang in the Cavern of Injustice" | `abbey` |
| `01` | `55/23` | Empath Abbey inner rooms | Dr. Cat: "While programming, I listen to the music of giants"; "Four shades of off green? Oh no!" | `abbey` |
| `1F` | `03/4C` | Zoltan's gypsy camp (forest) | "Huzzah! I am Zoltan, King of the Gypsies! This plate mail belonged to my grandfather" | `gypsy` |
| `21` | `05/E2` | Loubet's cave (cave merchant) | "Bonjour, my friend! Are you going to the Cavern of Injustice? Be careful not to step in the lava!" | `sidecave` |
| `29` | `05/B1` | spider-web cave | webs and a spider; no dialog | `sidecave` |
| `22` | (no warp leads here) | copy of Hatred `23` (same warps `1E->1B`, `E1->24`, drawn as a mushroom garden) | | `cavern` |
| `08*` | (from Injustice `04*`/`0A*`, not reached in play) | Injustice level | warps `11->04*`, `EF->0A*` | `injustice` |
| `44*` | `46*/D6` | gazer cave off the Abyss isle | | `abyss` |

## Not covered
- **Unnamed signs:** some sign texts in bank 4 (Beginner's Cave, Hero's Cave, Volcanic Cave,
  Dragon Cave, Lair of the Black Knight, Wishing Well) were not matched to an area. They are
  probably dungeon-level signs or belong to the two-player game. `$C511` swaps the surface list for
  `$7E95` `03 4C`, and Lord British says "Beneath my castle is a [dungeon] so dangerous none dare
  venture there alone" when you bring a companion. The two-player map was not explored.
