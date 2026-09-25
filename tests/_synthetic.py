"""Synthetic ROM images for ROM-free tests (never real game data)."""

from __future__ import annotations


def synthetic_rom(size: int = 0x20000, cart_type: int = 0x03) -> bytes:
    rom = bytearray([0xFF]) * size
    rom[0x0100:0x0104] = bytes([0x00, 0xC3, 0x50, 0x01])  # NOP; JP $0150
    rom[0x0134:0x0144] = b"SYNTHETIC TEST\x00\x00"
    rom[0x0143] = 0x00
    rom[0x0147] = cart_type
    rom[0x0148] = {0x8000: 0, 0x10000: 1, 0x20000: 2, 0x40000: 3}[size]
    rom[0x0149] = 0x02
    x = 0
    for i in range(0x0134, 0x014D):
        x = (x - rom[i] - 1) & 0xFF
    rom[0x014D] = x
    rom[0x014E] = rom[0x014F] = 0
    rom[0x014E:0x0150] = (sum(rom) & 0xFFFF).to_bytes(2, "big")
    return bytes(rom)
