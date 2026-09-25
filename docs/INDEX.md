# Ultima: Runes of Virtue DX — Documentation Index

Master index for ROM understanding and modification docs (same role as
penta-dragon-dx's `docs/INDEX.md`). Convention: dated investigation docs are
named `FINDINGS_YYYY_MM_DD_<topic>.md`, `PLAN_…`, `HANDOFF_…`; subsystem
references are lowercase `snake_case.md`.

## Start here

- [`rom_facts.md`](rom_facts.md) — verified dump hashes and header facts, with sources.
- [`../reverse_engineering/notes/TODO.md`](../reverse_engineering/notes/TODO.md) —
  reverse-engineering backlog that gates the builder.
- [`release/README.md`](release/README.md) — packaging rules (placeholder).
- [`release/known_deviations.md`](release/known_deviations.md) — accepted differences from the original.

## System architecture (to be written once the ROM is available)

- `interrupt_architecture.md` — bank map, ISRs, bank-shadow protocol
- `main_loop_and_entry.md` — boot → main loop
- `hram_allocation_map.md`, `wram_allocation_map.md` — memory ownership census
- `scene_state.md` — title / character select / overworld / dungeons / ending detection
- `bg_tile_architecture.md` — map/tile pipeline into VRAM
- `obj_pipeline.md` — shadow OAM and DMA
