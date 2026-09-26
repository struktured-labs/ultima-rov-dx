# Ultima: Runes of Virtue — verified ROM facts

Only facts confirmed from a cited source are listed. Anything else is marked
**unverified** and must be filled in from the actual ROM (`python3
scripts/check_rom.py` prints the header) — never from memory or forum posts.

## Supported dump (target of this project)

| Field | Value | Source |
|---|---|---|
| No-Intro name | `Ultima - Runes of Virtue (USA)` | [1] |
| File size | 131072 bytes (128 KiB) | [1] |
| CRC32 | `C44A0F1E` | [1] |
| MD5 | `411C3D168141D10EDDD93243F2A7765F` | [1], [2] |
| SHA-1 | `8D911CBBC6BD1518A85282DEF7F01D3ADD16E596` | [1], [2] |
| SHA-256 | `9008DF8D950B4E6966B38218E43BC3BAF9BAD91EF44B271B558AEE6F38C993D7` | [5] |

Other entries in the same DAT, recognized by `original_rom.py` so the error
message can name them, but **not supported**:

| Name | Size | CRC32 | MD5 | SHA-1 |
|---|---|---|---|---|
| Ultima - Ushinawareta Runes (Japan) | 131072 | `D2F94181` | `DD519F58F68E27B70C29CF19500A0154` | `3A1D88736E13436CDE15029DADD951B0B1C637E5` |
| Ultima - Runes of Virtue II (USA) (sequel) | 262144 | `C449FBBF` | `15CD267D7805FE9F1769E9644A9CEC2E` | `99C4FBF832EDB9B58960EC744AE784B55C7D63D2` |

## Cartridge / header

| Field | Value | Status |
|---|---|---|
| Header title (0x134–0x143) | `RUNES OF VIRTUE` | [5] |
| Cartridge type (0x147) / MBC | `0x06` = MBC2+BATTERY | [5]. MBC2 has 512×4-bit RAM built into the mapper, which matches the box's "battery back-up saves" [3]. |
| ROM size code (0x148) | `0x02` (128 KiB, 8 banks) | [5] |
| RAM size code (0x149) | `0x00` (expected for MBC2; the save RAM is inside the MBC2 chip) | [5] |
| CGB flag (0x143) / SGB flag (0x146) | `0x00` (DMG only) / `0x00` (no SGB support) | [5]; the SGB flag agrees with gbdb [3] |
| Mask ROM version (0x14C) | `0` | [5] |
| Header / global checksums | both OK | [5] |
| Part number | DMG-UT-USA | [3] |

## Game

| Field | Value | Source |
|---|---|---|
| Developer | Origin Systems | [4] |
| Publishers | JP: Pony Canyon; NA: FCI | [4] |
| Release | JP: 1991-12-14; NA: April 1992 | [4] |
| Characters | Mariah (Mage), Iolo (Bard), Dupre (Fighter), Shamino (Ranger) | [4] |
| Modes | 1 player; 2-player co-op/competitive via Game Link | [3], [2] |

## Sources

1. No-Intro "Nintendo - Game Boy" DAT, version `2026.08.01`, via the
   libretro-database mirror:
   `https://raw.githubusercontent.com/libretro/libretro-database/master/metadat/no-intro/Nintendo%20-%20Game%20Boy.dat`
   (fetched 2026-09-24). (DAT-o-MATIC itself did not return search results to
   an automated fetch.)
2. TASVideos, "Ultima: Runes of Virtue", game versions table:
   <https://tasvideos.org/Games/2999> (fetched 2026-09-24) — independently
   lists the same MD5/SHA-1 as "Good".
3. The Game Boy Database: <http://gbdb.org/games.php?title=Ultima%3A_Runes_of_Virtue>
   (box-back text, part number, SGB support, saves).
4. Wikipedia, "Ultima: Runes of Virtue":
   <https://en.wikipedia.org/wiki/Ultima:_Runes_of_Virtue> (fetched 2026-09-24).
5. `python3 scripts/check_rom.py` output for the local dump
   `rom/Ultima - Runes of Virtue (USA).gb`, which matches the DAT size, CRC32,
   MD5 and SHA-1 above (run 2026-09-26).
