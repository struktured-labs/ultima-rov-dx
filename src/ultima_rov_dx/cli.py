"""`rov-dx` command line: ROM-generic inspection and patch utilities.

Game-specific building lives in ``scripts/build_dx.py`` (mirrors
penta-dragon-dx, where production builders live under ``scripts/``).
This CLI never launches an emulator; use ``scripts/launch_mgba.sh``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from . import original_rom, palettes, patch_builder, rom_utils


def _print_header(hdr: dict) -> None:
    click.echo(f"  Title: {hdr['title']}")
    click.echo(f"  CGB: {hdr['cgb_support']} (flag=0x{hdr['cgb_flag']:02X})")
    click.echo(f"  SGB flag: 0x{hdr['sgb_flag']:02X}")
    click.echo(f"  Cart: {hdr['cartridge_type_name']} (0x{hdr['cartridge_type']:02X})")
    if hdr.get("rom_size_expected"):
        click.echo(f"  Declared ROM size: {hdr['rom_size_expected']} bytes (code 0x{hdr['rom_size_code']:02X})")
    if hdr.get("ram_size_expected") is not None:
        click.echo(f"  Declared RAM size: {hdr['ram_size_expected']} bytes (code 0x{hdr['ram_size_code']:02X})")
    click.echo(f"  Destination: 0x{hdr['destination_code']:02X}  Old licensee: 0x{hdr['old_licensee']:02X}  Version: {hdr['version']}")
    click.echo(f"  Header checksum: calc=0x{hdr['header_checksum_calc']:02X}, stored=0x{hdr['header_checksum']:02X}")
    click.echo(f"  Global checksum: calc=0x{hdr['global_checksum_calc']:04X}, stored=0x{hdr['global_checksum']:04X}")


@click.group()
def main() -> None:
    """Ultima: Runes of Virtue DX colorization toolkit."""


@main.command("check-rom")
@click.option("--rom", type=click.Path(dir_okay=False, path_type=Path), default=None,
              help=f"Defaults to rom/{original_rom.ORIGINAL_ROM_NAME} or ${original_rom.ROM_ENV_VAR}")
def check_rom(rom: Path | None) -> None:
    """Verify the original ROM is present and is the supported dump."""
    try:
        path, data = original_rom.require_original_rom(rom)
    except original_rom.RomError as exc:
        click.echo(str(exc), err=True)
        sys.exit(exc.status)
    ident = original_rom.identify(path)
    click.echo(f"OK: {path}")
    click.echo(f"  {ident.match.name}  size={ident.size}  crc32={ident.crc32}  sha256={ident.sha256}")
    _print_header(rom_utils.parse_header(data))


@main.command()
@click.option("--rom", type=click.Path(exists=True, dir_okay=False), required=True)
def verify(rom: str) -> None:
    """Print size, CRC32, and parsed header of any GB ROM."""
    info = rom_utils.inspect_rom(rom)
    click.echo(f"Size: {info['size']} bytes")
    click.echo(f"CRC32: {info['crc32']:08X}")
    if info.get("warning"):
        click.echo(f"Warning: {info['warning']}")
    if info.get("header"):
        click.echo("Header:")
        _print_header(info["header"])


@main.command()
@click.option("--rom", type=click.Path(exists=True, dir_okay=False), required=True)
@click.option("--free-min", type=int, default=128, help="Minimum free-space run length to report")
def analyze(rom: str, free_min: int) -> None:
    """Header, free-space regions, and CGB palette-register write candidates."""
    data = rom_utils.read_rom_bytes(rom)
    click.echo("Header summary:")
    _print_header(rom_utils.parse_header(data))
    regions = rom_utils.find_free_space(data, min_len=free_min)
    click.echo(f"\nFree-space regions (min {free_min} bytes), top 10 by length:")
    for r in regions[:10]:
        click.echo(f"  bank {r['bank']:02d} @0x{r['bank_addr']:04X} (file 0x{r['offset']:06X}), "
                   f"len={r['length']} pad=0x{r['pad']:02X}")
    hooks = rom_utils.find_palette_hook_candidates(data)
    click.echo(f"\nLDH [FF69]/[FF6B] byte-pattern candidates: {len(hooks)} (expected 0 for a DMG game)")


@main.command("check-palettes")
@click.argument("yaml_path", type=click.Path(exists=True, dir_okay=False))
def check_palettes(yaml_path: str) -> None:
    """Validate a palette YAML and print its encoded CRAM size."""
    encoded = palettes.encode(palettes.load(yaml_path))
    click.echo(f"OK: {len(encoded['bg'])} BG bytes ({', '.join(encoded['bg_names'])})")
    click.echo(f"OK: {len(encoded['obj'])} OBJ bytes ({', '.join(encoded['obj_names'])})")


@main.command("build-patch")
@click.option("--original", type=click.Path(exists=True), required=True)
@click.option("--modified", type=click.Path(exists=True), required=True)
@click.option("--out", type=click.Path(dir_okay=False), required=True)
def build_patch(original: str, modified: str, out: str) -> None:
    """Write an IPS patch from original -> modified."""
    patch = patch_builder.build_ips_patch(rom_utils.read_rom_bytes(original), rom_utils.read_rom_bytes(modified))
    Path(out).write_bytes(patch)
    click.echo(f"IPS patch written: {out} ({len(patch)} bytes)")


if __name__ == "__main__":
    main()
