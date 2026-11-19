#!/usr/bin/env python3
"""Apply the a44eb26 CHEATS patches to a built DX ROM (post-build, not a source flag).

The a44eb26 CHEATS ROM (md5 50fd75114e975dbf9250f1b2efe64100) differs from
plain a44eb26 in four bytes: three opcode swaps and the global checksum.

  bank0 $0B5B  EA 20 D1  LD [$D120],A  ->  FA 20 D1  LD A,[$D120]
  bank0 $3011  EA 29 D1  LD [$D129],A  ->  FA 29 D1  LD A,[$D129]
  bank1 $51BA  EA 29 D1  LD [$D129],A  ->  FA 29 D1  LD A,[$D129]

$D120 is BCD gold (add path caps at $99 / 99). The $0B5B store is the pay/
spend path (cp price; ret c; sub; daa; write). After the patch, spends still
succeed but gold is not written back, so it stays at its current value.

$D129 is the star/energy count (max at $D12A, same pattern as HP at
$D127/$D128). The two stores are the subtract/floor-at-zero paths; after the
patch those spends and drains no longer stick.

The earlier 836b9f7 INFMONEY build patched only $0B5B (gold). CHEATS includes
that plus the two $D129 sites.

The global checksum at $14E-$14F is recomputed. No source bytes other than
those opcodes are changed, so this applies cleanly to 2ca3353 (same preimage
at those offsets as a44eb26).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# (file offset, preimage, patched)
PATCHES: list[tuple[int, bytes, bytes]] = [
    (0x0B5B, bytes([0xEA, 0x20, 0xD1]), bytes([0xFA, 0x20, 0xD1])),
    (0x3011, bytes([0xEA, 0x29, 0xD1]), bytes([0xFA, 0x29, 0xD1])),
    (0x51BA, bytes([0xEA, 0x29, 0xD1]), bytes([0xFA, 0x29, 0xD1])),
]


def fix_global_checksum(data: bytes) -> bytes:
    rom = bytearray(data)
    rom[0x014E] = rom[0x014F] = 0
    total = sum(rom) & 0xFFFF
    rom[0x014E:0x0150] = total.to_bytes(2, "big")
    return bytes(rom)


def apply_cheats(rom: bytes) -> bytes:
    out = bytearray(rom)
    for off, old, new in PATCHES:
        have = bytes(out[off:off + len(old)])
        if have == new:
            continue
        if have != old:
            raise ValueError(
                f"unexpected bytes at file+0x{off:04X}: {have.hex()} "
                f"(want {old.hex()} or already {new.hex()})"
            )
        out[off:off + len(new)] = new
    return fix_global_checksum(bytes(out))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("rom", type=Path, help="input DX .gbc (e.g. the 2ca3353 build)")
    p.add_argument("-o", "--output", type=Path, required=True, help="patched CHEATS .gbc")
    args = p.parse_args()
    data = args.rom.read_bytes()
    try:
        out = apply_cheats(data)
    except ValueError as exc:
        print(f"apply_cheats: {exc}", file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(out)
    print(f"wrote {args.output} ({len(out)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
