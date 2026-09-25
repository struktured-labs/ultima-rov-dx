"""Tiny hand-assembly helper for SM83 (Game Boy CPU) routines.

Ported from penta-dragon-dx (`_Asm` in scripts/arena_position.py): routines
are emitted as raw bytes by Python builders rather than through an
assembler toolchain. Only generic, game-independent routines live here.
"""

from __future__ import annotations


class Asm:
    def __init__(self) -> None:
        self.code = bytearray()
        self.labels: dict[str, int] = {}
        self.fwd: list[tuple[int, str]] = []

    def db(self, *items: int | bytes | bytearray | list[int]) -> "Asm":
        for item in items:
            if isinstance(item, (list, bytes, bytearray)):
                self.code.extend(item)
            else:
                self.code.append(item & 0xFF)
        return self

    def label(self, name: str) -> "Asm":
        self.labels[name] = len(self.code)
        return self

    def jr(self, opcode: int, name: str) -> "Asm":
        """Emit JR/JR cc (0x18, 0x20, 0x28, 0x30, 0x38) to a label."""
        if name in self.labels:
            off = self.labels[name] - (len(self.code) + 2)
            assert -128 <= off <= 127, f"JR {name} out of range: {off}"
            self.db(opcode, off & 0xFF)
        else:
            self.db(opcode, 0x00)
            self.fwd.append((len(self.code) - 1, name))
        return self

    def finish(self) -> bytes:
        for pos, name in self.fwd:
            off = self.labels[name] - (pos + 1)
            assert -128 <= off <= 127, f"fwd JR {name} out of range: {off}"
            self.code[pos] = off & 0xFF
        return bytes(self.code)


def cram_loader(data_addr: int) -> bytes:
    """Load 64 BG + 64 OBJ palette bytes from ``data_addr`` into CGB CRAM.

    Game-independent: no bank switching, so ``data_addr`` must be visible
    in the currently mapped bank when this runs (bank 0, or the caller's
    bank). It does not detect DMG vs CGB; gating on the boot-time A=$11
    value is the caller's job (TODO: game-specific, see
    reverse_engineering/notes/TODO.md).
    CRAM is only writable outside mode 3, so call during VBlank or with
    the LCD off. Clobbers AF, BC, HL.
    """
    a = Asm()
    a.db(0x21, data_addr & 0xFF, (data_addr >> 8) & 0xFF)  # LD HL,data
    for index_reg, data_reg in ((0x68, 0x69), (0x6A, 0x6B)):
        a.db(0x3E, 0x80, 0xE0, index_reg)                  # LD A,$80; LDH [BCPS/OCPS],A
        a.db(0x06, 64)                                      # LD B,64
        a.label(f"loop_{data_reg:x}")
        a.db(0x2A, 0xE0, data_reg)                          # LD A,[HL+]; LDH [BCPD/OCPD],A
        a.db(0x05)                                          # DEC B
        a.jr(0x20, f"loop_{data_reg:x}")                   # JR NZ,loop
    a.db(0xC9)                                              # RET
    return a.finish()
