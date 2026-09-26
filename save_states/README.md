# save_states/

Local mGBA/PyBoy save states for agents and probes (equivalent of
penta-dragon-dx's `save_states_for_claude/`). Contents are gitignored: states
embed copyrighted RAM/VRAM and are tied to exact ROM builds. Record in this
README which ROM SHA-256 and scene each state was taken from.

## Current states (PyBoy `save_state` format, written by `scripts/capture_screens.py`)

Regenerate with `uv run python scripts/capture_screens.py` (default
`--states save_states`). `og_*` = original ROM (SHA-256 9008df8d...c993d7,
DMG mode); `dx_*` = `rom/working/ultima_rov_dx.gbc` in CGB mode. **DX states
embed the WRAM-bank-2 runtime of the build they were made with**, so after any
change to `dx.asm` or the tables, rerun the capture script before using them.
Built from DX SHA-256 7627ea3fe5b5922e6b69ed8f058a57a7d545b7812157d5de865db3934946c9da (2026-09-26).
Champion: Iolo the Bard, difficulty Medium, initials AAA.

| State | Scene |
|---|---|
| `*_cavern_entrance.state` | Cavern of Hatred just entered (area $18, player on the up-ladder, cell $66) |
| `*_cavern_level1.state` | two cells south of the entrance ladder (area $18) |
| `*_cavern_level2.state` | level 2 arrival (area $19, cell $9E) |
| `*_cavern_level2_arrows.state` | level 2 arrow-floor corridor, rat and heart pickup in view |
| `*_cavern_level3.state` | level 3 arrival (area $1A, cell $0D) |

Load in PyBoy: `pb = PyBoy(rom, cgb=True); pb.load_state(open(path, "rb"))`.
