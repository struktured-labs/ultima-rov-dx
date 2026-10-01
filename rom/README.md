# rom/

Place your own dump of the original cartridge here:

    rom/Ultima - Runes of Virtue (USA).gb

- Size 131072 bytes, MD5 `411c3d168141d10eddd93243f2a7765f`,
  SHA-1 `8d911cbbc6bd1518a85282def7f01d3add16e596`, CRC32 `c44a0f1e`
  (No-Intro; see `docs/rom_facts.md`).
- Everything in `rom/` except this README and `ultima_rov_dx.ips` is gitignored; the ROM is never committed and this project never
  downloads it. Check it with `python3 scripts/check_rom.py`.
- Alternatively set `ULTIMA_ROV_ROM=/absolute/path.gb`.

Build outputs:

- `rom/working/ultima_rov_dx.gbc` — patched ROM (gitignored)
- `rom/ultima_rov_dx.ips` — ROM-free distribution patch (committed here and attached to GitHub Releases)
