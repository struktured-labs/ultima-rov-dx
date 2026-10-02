#!/usr/bin/env python3
"""Production builder for Ultima: Runes of Virtue DX.

Pure Python, like penta-dragon-dx: loads the verified original ROM plus the
palette/category YAML, assembles src/ultima_rov_dx/asm/dx.asm with the
in-repo SM83 assembler (src/ultima_rov_dx/sm83asm.py), verifies every
overwritten byte against game_layout preimages, expands the ROM to 256 KiB
(MBC2 maximum), and writes a CGB-enhanced ROM plus a ROM-free IPS patch.

Stages:
  1. validate palette + category YAML (ROM-free)
  2. report reverse-engineering readiness (ROM-free; src/ultima_rov_dx/game_layout.py)
  3. require and verify rom/Ultima - Runes of Virtue (USA).gb   -> exit 66/65 if missing/wrong
  4. patch (src/ultima_rov_dx/dx_patch.py)                      -> exit 78 if RE facts missing
  5. write rom/working/ultima_rov_dx.gbc + rom/ultima_rov_dx.ips

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

import yaml  # noqa: E402

from ultima_rov_dx import dx_patch, game_layout, original_rom, palettes, patch_builder, rom_utils  # noqa: E402

EXIT_RE_INCOMPLETE = 78  # sysexits EX_CONFIG
DEFAULT_PALETTES = ROOT / "palettes" / "rov_palettes.yaml"
DEFAULT_BG_CATEGORIES = ROOT / "palettes" / "bg_tile_categories.yaml"
DEFAULT_OBJ_CATEGORIES = ROOT / "palettes" / "obj_categories.yaml"
DEFAULT_BRANDING = ROOT / "palettes" / "branding.yaml"
DEFAULT_OUT = ROOT / "rom" / "working" / "ultima_rov_dx.gbc"
DEFAULT_IPS = ROOT / "rom" / "ultima_rov_dx.ips"
HEADER_ONLY_OUT = ROOT / "tmp" / "ultima_rov_dx_header_only.gb"


class IncompleteReverseEngineering(Exception):
    pass


def load_inputs(pal_path: Path = DEFAULT_PALETTES, bg_path: Path = DEFAULT_BG_CATEGORIES,
                obj_path: Path = DEFAULT_OBJ_CATEGORIES, brand_path: Path | None = DEFAULT_BRANDING) -> dict:
    """Load and validate the YAML inputs (ROM-free)."""

    pal = palettes.load(pal_path)
    with open(bg_path, encoding="utf-8") as fh:
        bg = yaml.safe_load(fh) or {}
    with open(obj_path, encoding="utf-8") as fh:
        obj = yaml.safe_load(fh) or {}
    dx_patch.build_tables(pal, bg, obj)  # raises on bad names/ranges
    brand = None
    if brand_path is not None and brand_path.is_file():
        with open(brand_path, encoding="utf-8") as fh:
            brand = yaml.safe_load(fh) or None
    return {"palettes": pal, "bg_categories": bg, "obj_categories": obj, "branding": brand}


def build(original: bytes, inputs: dict, header_only: bool = False) -> bytes:
    """Return the patched ROM image. Pure function of its inputs."""

    if header_only:
        rom = rom_utils.set_cgb_supported(bytes(original))  # 0x143 |= 0x80
        rom = rom_utils.fix_header_checksum(rom)
        return rom_utils.fix_global_checksum(rom)
    missing = game_layout.missing_facts()
    if missing:
        raise IncompleteReverseEngineering("game-specific facts still unknown: " + ", ".join(missing))
    out, _ = dx_patch.build(original, inputs["palettes"], inputs["bg_categories"], inputs["obj_categories"],
                            inputs.get("branding"))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rom", type=Path, default=None, help="original ROM (default: rom/<No-Intro name>.gb)")
    parser.add_argument("--palettes", type=Path, default=DEFAULT_PALETTES)
    parser.add_argument("--bg-categories", type=Path, default=DEFAULT_BG_CATEGORIES)
    parser.add_argument("--obj-categories", type=Path, default=DEFAULT_OBJ_CATEGORIES)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--ips", type=Path, default=DEFAULT_IPS)
    parser.add_argument("--header-only", action="store_true",
                        help="only set the CGB flag + checksums (writes to tmp/, no IPS)")
    args = parser.parse_args()
    sys.stdout.reconfigure(line_buffering=True)  # keep progress ordered with stderr

    print(f"[1/5] palettes: {args.palettes.relative_to(ROOT) if args.palettes.is_relative_to(ROOT) else args.palettes}")
    try:
        inputs = load_inputs(args.palettes, args.bg_categories, args.obj_categories)
    except (ValueError, dx_patch.PatchError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 65
    encoded = palettes.encode(inputs["palettes"])
    print(f"      OK ({len(encoded['bg'])} BG + {len(encoded['obj'])} OBJ CRAM bytes, categories valid)")

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
        patched = build(original, inputs, header_only=args.header_only)
    except dx_patch.PatchError as exc:
        print(f"ERROR: patch refused: {exc}", file=sys.stderr)
        return 65
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
