# Ultima: Runes of Virtue DX

An in-progress (just scaffolded) Game Boy Color conversion of *Ultima: Runes
of Virtue* (Game Boy; Origin Systems; JP Pony Canyon Dec 1991, NA FCI 1992).

The goal mirrors [Penta Dragon DX](https://github.com/struktured-labs/penta-dragon-dx):
add scene-aware color while keeping the original's movement, music, maps,
and timing. The result is a DMG-compatible, CGB-enhanced ROM distributed as a
ROM-free IPS patch.

## Current status

**Scaffold only — no colorization yet.** Reverse engineering has not started
because the original ROM has not been supplied.

- Tooling works without the ROM: palette YAML validation, ROM
  identification, header/checksum/IPS utilities, mGBA single-flight guard,
  unit tests.
- `scripts/build_dx.py` validates palettes, reports which game facts are
  still unknown, then stops with a clear error if the ROM is missing
  (exit 66) or, once it is present, until the game hooks are reverse
  engineered (exit 78).
- Game-specific work is tracked in
  [`reverse_engineering/notes/TODO.md`](reverse_engineering/notes/TODO.md).

The ROM is intentionally not stored in this repository.

## Build and play

You need your own USA ROM at `rom/Ultima - Runes of Virtue (USA).gb`.
Its MD5 must be `411c3d168141d10eddd93243f2a7765f`
(SHA-1 `8d911cbbc6bd1518a85282def7f01d3add16e596`; see
[`docs/rom_facts.md`](docs/rom_facts.md)).

```bash
uv sync --extra emu                         # python deps (+ PyBoy for probes)
python3 scripts/check_rom.py                # verify the ROM and print its header
uv run python scripts/build_dx.py           # -> rom/working/ultima_rov_dx.gb + rom/ultima_rov_dx.ips
uv run python scripts/launch_gate.py rom/working/ultima_rov_dx.gb   # boots to a non-blank screen?
scripts/launch_mgba.sh rom/working/ultima_rov_dx.gb                 # guarded headed play
```

The launcher is deliberate: it goes through a project-wide single-flight
lock so emulator processes never pile up (see `AGENTS.md`).

`uv run python scripts/build_dx.py --header-only` is a plumbing test: it only
sets the CGB flag and checksums (output in `tmp/`). Expect a blank screen,
since CGB mode ignores the DMG palette registers until palettes are loaded.

## Colors

Colors are defined in YAML rather than hand-edited ROM bytes:

- `palettes/rov_palettes.yaml` — 8 BG + 8 OBJ CGB palettes (placeholder grayscale)
- `palettes/bg_tile_categories.yaml` — BG tile ID → material category (empty)

```bash
uv run rov-dx check-palettes palettes/rov_palettes.yaml
```

## Verification

```bash
uv run python -m unittest discover -s tests -v
python3 scripts/diagnostics/verify_mgba_singleflight_guard.py
scripts/install_git_hooks.sh               # enable .githooks/pre-commit
```

## Distribution

This repository will contain source code, palette data, verification tools,
and a ROM-free IPS patch. It does not contain the original or modified game
ROM, save files, or emulator states.

*Ultima: Runes of Virtue* is owned by its original rights holders. Ultima:
Runes of Virtue DX is an unofficial fan project.
