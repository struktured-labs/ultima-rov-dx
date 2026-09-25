#!/usr/bin/env python3
"""Verify the user-supplied original ROM (presence, size, MD5/SHA1) and print its header.

Exit 0 = supported dump present; 66 = missing; 65 = wrong/unsupported dump.
Equivalent to `uv run rov-dx check-rom`, but runnable with bare python3 + no deps.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ultima_rov_dx import original_rom, rom_utils  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=None)
    args = parser.parse_args()
    try:
        path, data = original_rom.require_original_rom(args.rom)
    except original_rom.RomError as exc:
        print(str(exc), file=sys.stderr)
        return exc.status
    ident = original_rom.identify(path)
    hdr = rom_utils.parse_header(data)
    print(f"OK: {path}")
    print(f"  dump:   {ident.match.name}")
    print(f"  size:   {ident.size}  crc32={ident.crc32}  md5={ident.md5.lower()}")
    print(f"  sha1:   {ident.sha1.lower()}")
    print(f"  sha256: {ident.sha256}")
    print(f"  header: title={hdr['title']!r} cart=0x{hdr['cartridge_type']:02X} ({hdr['cartridge_type_name']}) "
          f"rom_code=0x{hdr['rom_size_code']:02X} ram_code=0x{hdr['ram_size_code']:02X} "
          f"cgb=0x{hdr['cgb_flag']:02X} sgb=0x{hdr['sgb_flag']:02X} version={hdr['version']}")
    print(f"  checksums: header {'OK' if hdr['header_checksum'] == hdr['header_checksum_calc'] else 'MISMATCH'}, "
          f"global {'OK' if hdr['global_checksum'] == hdr['global_checksum_calc'] else 'MISMATCH'}")
    print("  -> record these header values (with this output as the source) in docs/rom_facts.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
