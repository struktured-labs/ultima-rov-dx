#!/usr/bin/env python3
"""Production builder for Ultima: Runes of Virtue DX.

Mirrors penta-dragon-dx's approach: a pure-Python binary patcher (no
assembler toolchain) that loads the verified original ROM plus palette
YAML, installs hand-assembled SM83 routines, sets the CGB header flag, and
writes a working ROM and a ROM-free IPS patch.

Stages:
  1. validate palette YAML (ROM-free)
  2. report reverse-engineering readiness (ROM-free; src/ultima_rov_dx/game_layout.py)
  3. require and verify rom/Ultima - Runes of Virtue (USA).gb   -> exit 66/65 if missing/wrong
  4. patch (currently: header only -- game hooks are TODO)       -> exit 78 until RE is done
  5. write rom/working/ultima_rov_dx.gb + rom/ultima_rov_dx.ips

Usage:
  uv run python scripts/build_dx.py
  uv run python scripts/build_dx.py --header-only   # plumbing test; CGB-flagged ROM will show a blank screen
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ultima_rov_dx import game_layout, original_rom, palettes, patch_builder, rom_utils  # noqa: E402

EXIT_RE_INCOMPLETE = 78  # sysexits EX_CONFIG
DEFAULT_PALETTES = ROOT / "palettes" / "rov_palettes.yaml"
DEFAULT_OUT = ROOT / "rom" / "working" / "ultima_rov_dx.gb"
DEFAULT_IPS = ROOT / "rom" / "ultima_rov_dx.ips"
HEADER_ONLY_OUT = ROOT / "tmp" / "ultima_rov_dx_header_only.gb"


class IncompleteReverseEngineering(Exception):
    pass


def build(original: bytes, encoded: dict, header_only: bool = False) -> bytes:
    """Return the patched ROM image. Pure function; unit-tested with synthetic ROMs."""

    rom = bytearray(original)
    if not header_only:
        missing = game_layout.missing_facts()
        if missing:
            raise IncompleteReverseEngineering(
                "game-specific facts still unknown: " + ", ".join(missing)
            )
        # TODO(RE): once PALETTE_INIT_HOOK / FREE_SPACE are known:
        #   - verify hook preimage bytes exactly (fail closed on mismatch)
        #   - place encoded['bg'] + encoded['obj'] and asm.cram_loader() in free space
        #   - redirect the hook with CALL/JP, preserving displaced instructions
        #   - then VBlank / tilemap-attribute / OAM-palette services
        raise IncompleteReverseEngineering("patch installation not implemented yet")
    rom = bytearray(rom_utils.set_cgb_supported(bytes(rom)))  # 0x143 |= 0x80 (CGB-enhanced, DMG-compatible)
    rom = bytearray(rom_utils.fix_header_checksum(bytes(rom)))
    rom = bytearray(rom_utils.fix_global_checksum(bytes(rom)))
    return bytes(rom)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rom", type=Path, default=None, help="original ROM (default: rom/<No-Intro name>.gb)")
    parser.add_argument("--palettes", type=Path, default=DEFAULT_PALETTES)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--ips", type=Path, default=DEFAULT_IPS)
    parser.add_argument("--header-only", action="store_true",
                        help="only set the CGB flag + checksums (writes to tmp/, no IPS)")
    args = parser.parse_args()
    sys.stdout.reconfigure(line_buffering=True)  # keep progress ordered with stderr

    print(f"[1/5] palettes: {args.palettes.relative_to(ROOT) if args.palettes.is_relative_to(ROOT) else args.palettes}")
    encoded = palettes.encode(palettes.load(args.palettes))
    print(f"      OK ({len(encoded['bg'])} BG + {len(encoded['obj'])} OBJ CRAM bytes)")

    missing = game_layout.missing_facts()
    print("[2/5] reverse-engineering readiness: "
          + ("complete" if not missing else "INCOMPLETE -- unknown: " + ", ".join(missing)))

    print("[3/5] original ROM")
    try:
        rom_path, original = original_rom.require_original_rom(args.rom)
    except original_rom.RomError as exc:
        print(str(exc), file=sys.stderr)
        return exc.status
    print(f"      OK {rom_path} ({original_rom.identify(rom_path).match.name})")

    print("[4/5] patch" + (" (header only)" if args.header_only else ""))
    try:
        patched = build(original, encoded, header_only=args.header_only)
    except IncompleteReverseEngineering as exc:
        print(f"ERROR: cannot build the DX ROM yet: {exc}.\n"
              "  Fill in src/ultima_rov_dx/game_layout.py (see reverse_engineering/notes/TODO.md),\n"
              "  or pass --header-only for a plumbing test.", file=sys.stderr)
        return EXIT_RE_INCOMPLETE

    out = args.out or (HEADER_ONLY_OUT if args.header_only else DEFAULT_OUT)
    print(f"[5/5] write {out}")
    rom_utils.write_rom_bytes(out, patched)
    print(f"      size={len(patched)} sha256={hashlib.sha256(patched).hexdigest()}")
    if not args.header_only:
        args.ips.write_bytes(patch_builder.build_ips_patch(original, patched))
        print(f"      IPS {args.ips}")
    else:
        print("      NOTE: header-only ROM runs in CGB mode without palettes -> expect a blank screen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
