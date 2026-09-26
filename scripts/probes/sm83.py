#!/usr/bin/env python3
"""Minimal SM83 (Game Boy CPU) interpreter for reverse-engineering traces.

Not an emulator: the PPU is reduced to an LY counter (+ STAT mode bits and
VBlank/STAT-LYC interrupts), there is no audio, timer, or serial. It is good
enough to resume a PyBoy save state for a few frames and answer "which PC
wrote to address X" (write watchpoints), which PyBoy's public API cannot do.

Memory model: MBC2 (this game): ROM bank select via writes to 0x0000-0x3FFF
with address bit 8 set; 512x4-bit RAM at A000-A1FF (mirrored).
"""

from __future__ import annotations

from typing import Callable

R8 = ("b", "c", "d", "e", "h", "l", None, "a")


class CPU:
    def __init__(self, rom: bytes):
        self.rom = rom
        self.bank = 1
        self.mem = bytearray(0x10000)  # 0x8000-0xFFFF used
        self.ram = bytearray(0x200)
        self.a = self.f = self.b = self.c = self.d = self.e = self.h = self.l = 0
        self.sp = 0xFFFE
        self.pc = 0x100
        self.ime = True
        self.ime_pending = False
        self.halted = False
        self.cycles = 0  # M-cycles
        self.keys = 0     # bit0..7 = right,left,up,down,a,b,select,start
        self.write_watch: list[tuple[int, int, Callable]] = []
        self.cur_pc = 0

    # ---- memory -------------------------------------------------------
    def ly(self) -> int:
        return (self.cycles // 114) % 154

    def rd(self, addr: int) -> int:
        addr &= 0xFFFF
        if addr < 0x4000:
            return self.rom[addr]
        if addr < 0x8000:
            off = (self.bank % (len(self.rom) // 0x4000)) * 0x4000 + addr - 0x4000
            return self.rom[off]
        if 0xA000 <= addr < 0xC000:
            return self.ram[addr & 0x1FF] | 0xF0
        if 0xE000 <= addr < 0xFE00:
            addr -= 0x2000
        if addr == 0xFF44:
            return self.ly()
        if addr == 0xFF41:
            ly = self.ly()
            dot = self.cycles % 114
            mode = 1 if ly >= 144 else (2 if dot < 20 else (3 if dot < 63 else 0))
            return (self.mem[addr] & 0xF8) | mode | (4 if ly == self.mem[0xFF45] else 0) | 0x80
        if addr == 0xFF00:
            sel = self.mem[0xFF00]
            v = 0x0F
            if not sel & 0x10:
                v &= ~(self.keys & 0x0F)
            if not sel & 0x20:
                v &= ~((self.keys >> 4) & 0x0F)
            return 0xC0 | (sel & 0x30) | (v & 0x0F)
        return self.mem[addr]

    def wr(self, addr: int, val: int) -> None:
        addr &= 0xFFFF
        val &= 0xFF
        for lo, hi, cb in self.write_watch:
            if lo <= addr < hi:
                cb(self, addr, val)
        if addr < 0x4000:
            if addr & 0x100:
                self.bank = (val & 0x0F) or 1
            return
        if addr < 0x8000:
            return
        if 0xA000 <= addr < 0xC000:
            self.ram[addr & 0x1FF] = val & 0x0F
            return
        if 0xE000 <= addr < 0xFE00:
            addr -= 0x2000
        if addr == 0xFF46:  # OAM DMA (instant)
            src = val << 8
            for i in range(0xA0):
                self.mem[0xFE00 + i] = self.rd(src + i)
        self.mem[addr] = val

    def fetch(self) -> int:
        v = self.rd(self.pc)
        self.pc = (self.pc + 1) & 0xFFFF
        return v

    def fetch16(self) -> int:
        lo = self.fetch()
        return lo | (self.fetch() << 8)

    # ---- registers ------------------------------------------------------
    def get_r(self, i: int) -> int:
        if i == 6:
            return self.rd(self.hl)
        return getattr(self, R8[i])

    def set_r(self, i: int, v: int) -> None:
        if i == 6:
            self.wr(self.hl, v)
        else:
            setattr(self, R8[i], v & 0xFF)

    @property
    def hl(self): return (self.h << 8) | self.l
    @hl.setter
    def hl(self, v): self.h, self.l = (v >> 8) & 0xFF, v & 0xFF
    @property
    def bc(self): return (self.b << 8) | self.c
    @bc.setter
    def bc(self, v): self.b, self.c = (v >> 8) & 0xFF, v & 0xFF
    @property
    def de(self): return (self.d << 8) | self.e
    @de.setter
    def de(self, v): self.d, self.e = (v >> 8) & 0xFF, v & 0xFF
    @property
    def af(self): return (self.a << 8) | self.f
    @af.setter
    def af(self, v): self.a, self.f = (v >> 8) & 0xFF, v & 0xF0

    def get_rr(self, i):  # bc de hl sp
        return (self.bc, self.de, self.hl, self.sp)[i]

    def set_rr(self, i, v):
        v &= 0xFFFF
        if i == 0: self.bc = v
        elif i == 1: self.de = v
        elif i == 2: self.hl = v
        else: self.sp = v

    def flag(self, z, n, h, c):
        self.f = (z << 7) | (n << 6) | (h << 5) | (c << 4)

    @property
    def zf(self): return (self.f >> 7) & 1
    @property
    def cf(self): return (self.f >> 4) & 1

    def push(self, v):
        self.sp = (self.sp - 1) & 0xFFFF; self.wr(self.sp, v >> 8)
        self.sp = (self.sp - 1) & 0xFFFF; self.wr(self.sp, v & 0xFF)

    def pop(self):
        lo = self.rd(self.sp); self.sp = (self.sp + 1) & 0xFFFF
        hi = self.rd(self.sp); self.sp = (self.sp + 1) & 0xFFFF
        return lo | (hi << 8)

    def cond(self, i):
        return (not self.zf, self.zf, not self.cf, self.cf)[i]

    # ---- ALU ------------------------------------------------------------
    def alu(self, op, v):
        a = self.a
        if op == 0:  # add
            r = a + v; self.flag((r & 0xFF) == 0, 0, (a & 0xF) + (v & 0xF) > 0xF, r > 0xFF); self.a = r & 0xFF
        elif op == 1:  # adc
            c = self.cf; r = a + v + c
            self.flag((r & 0xFF) == 0, 0, (a & 0xF) + (v & 0xF) + c > 0xF, r > 0xFF); self.a = r & 0xFF
        elif op == 2 or op == 7:  # sub / cp
            r = a - v; self.flag((r & 0xFF) == 0, 1, (a & 0xF) < (v & 0xF), r < 0)
            if op == 2: self.a = r & 0xFF
        elif op == 3:  # sbc
            c = self.cf; r = a - v - c
            self.flag((r & 0xFF) == 0, 1, (a & 0xF) < (v & 0xF) + c, r < 0); self.a = r & 0xFF
        elif op == 4:
            self.a = a & v; self.flag(self.a == 0, 0, 1, 0)
        elif op == 5:
            self.a = a ^ v; self.flag(self.a == 0, 0, 0, 0)
        elif op == 6:
            self.a = a | v; self.flag(self.a == 0, 0, 0, 0)

    def cb(self):
        op = self.fetch()
        x, y, z = op >> 6, (op >> 3) & 7, op & 7
        v = self.get_r(z)
        cyc = 4 if z == 6 else 2
        if x == 0:
            c = self.cf
            if y == 0: r = ((v << 1) | (v >> 7)) & 0xFF; nc = v >> 7
            elif y == 1: r = ((v >> 1) | (v << 7)) & 0xFF; nc = v & 1
            elif y == 2: r = ((v << 1) | c) & 0xFF; nc = v >> 7
            elif y == 3: r = (v >> 1) | (c << 7); nc = v & 1
            elif y == 4: r = (v << 1) & 0xFF; nc = v >> 7
            elif y == 5: r = (v >> 1) | (v & 0x80); nc = v & 1
            elif y == 6: r = ((v << 4) | (v >> 4)) & 0xFF; nc = 0
            else: r = v >> 1; nc = v & 1
            self.flag(r == 0, 0, 0, nc); self.set_r(z, r)
        elif x == 1:
            self.f = (self.f & 0x10) | 0x20 | (0 if (v >> y) & 1 else 0x80)
            cyc = 3 if z == 6 else 2
        elif x == 2:
            self.set_r(z, v & ~(1 << y))
        else:
            self.set_r(z, v | (1 << y))
        return cyc

    # ---- step -----------------------------------------------------------
    def interrupt(self):
        pend = self.mem[0xFFFF] & self.mem[0xFF0F] & 0x1F
        if not pend:
            return False
        self.halted = False
        if not self.ime:
            return False
        for i in range(5):
            if pend & (1 << i):
                self.mem[0xFF0F] &= ~(1 << i)
                self.ime = False
                self.push(self.pc)
                self.pc = 0x40 + 8 * i
                self.cycles += 5
                return True
        return False

    def tick_ppu(self, before, after):
        lcd_on = self.mem[0xFF40] & 0x80
        for c in range(before // 114, after // 114):
            ly = (c + 1) % 154
            if ly == 144 and lcd_on:
                self.mem[0xFF0F] |= 1
            if lcd_on and (self.mem[0xFF41] & 0x40) and ly == self.mem[0xFF45]:
                self.mem[0xFF0F] |= 2

    def step(self):
        before = self.cycles
        if self.ime_pending:
            self.ime = True; self.ime_pending = False
        self.interrupt()
        if self.halted:
            self.cycles += 1
        else:
            self.cur_pc = self.pc
            self.cycles += self.execute(self.fetch())
        self.tick_ppu(before, self.cycles)

    def execute(self, op):  # noqa: C901
        x, y, z = op >> 6, (op >> 3) & 7, op & 7
        p, q = y >> 1, y & 1
        if x == 1:
            if op == 0x76:
                self.halted = True; return 1
            self.set_r(y, self.get_r(z)); return 2 if (y == 6 or z == 6) else 1
        if x == 2:
            self.alu(y, self.get_r(z)); return 2 if z == 6 else 1
        if x == 0:
            if z == 0:
                if y == 0: return 1
                if y == 1:
                    a = self.fetch16(); self.wr(a, self.sp & 0xFF); self.wr(a + 1, self.sp >> 8); return 5
                if y == 2: self.fetch(); return 1  # STOP
                d = self.fetch(); d = d - 256 if d > 127 else d
                if y == 3 or self.cond(y - 4):
                    self.pc = (self.pc + d) & 0xFFFF; return 3
                return 2
            if z == 1:
                if q == 0: self.set_rr(p, self.fetch16()); return 3
                hl = self.hl; v = self.get_rr(p); r = hl + v
                self.f = (self.f & 0x80) | (0x20 if (hl & 0xFFF) + (v & 0xFFF) > 0xFFF else 0) | (0x10 if r > 0xFFFF else 0)
                self.hl = r; return 2
            if z == 2:
                addr = (self.bc, self.de, self.hl, self.hl)[p]
                if q == 0: self.wr(addr, self.a)
                else: self.a = self.rd(addr)
                if p == 2: self.hl = self.hl + 1
                elif p == 3: self.hl = self.hl - 1
                return 2
            if z == 3:
                self.set_rr(p, self.get_rr(p) + (1 if q == 0 else -1)); return 2
            if z == 4 or z == 5:
                v = self.get_r(y)
                if z == 4:
                    r = (v + 1) & 0xFF; self.f = (self.f & 0x10) | (0x80 if r == 0 else 0) | (0x20 if (v & 0xF) == 0xF else 0)
                else:
                    r = (v - 1) & 0xFF; self.f = (self.f & 0x10) | 0x40 | (0x80 if r == 0 else 0) | (0x20 if (v & 0xF) == 0 else 0)
                self.set_r(y, r); return 3 if y == 6 else 1
            if z == 6:
                self.set_r(y, self.fetch()); return 3 if y == 6 else 2
            # z == 7
            a, c = self.a, self.cf
            if y == 0: self.a = ((a << 1) | (a >> 7)) & 0xFF; self.flag(0, 0, 0, a >> 7)
            elif y == 1: self.a = ((a >> 1) | (a << 7)) & 0xFF; self.flag(0, 0, 0, a & 1)
            elif y == 2: self.a = ((a << 1) | c) & 0xFF; self.flag(0, 0, 0, a >> 7)
            elif y == 3: self.a = (a >> 1) | (c << 7); self.flag(0, 0, 0, a & 1)
            elif y == 4:  # DAA
                n, h = (self.f >> 6) & 1, (self.f >> 5) & 1
                if not n:
                    if c or a > 0x99: a += 0x60; c = 1
                    if h or (a & 0xF) > 9: a += 6
                else:
                    if c: a -= 0x60
                    if h: a -= 6
                a &= 0xFF; self.a = a; self.f = (0x80 if a == 0 else 0) | (n << 6) | (c << 4)
            elif y == 5: self.a = a ^ 0xFF; self.f = (self.f & 0x90) | 0x60
            elif y == 6: self.f = (self.f & 0x80) | 0x10
            else: self.f = (self.f & 0x80) | ((c ^ 1) << 4)
            return 1
        # x == 3
        if z == 0:
            if y < 4:
                if self.cond(y): self.pc = self.pop(); return 5
                return 2
            if y == 4: self.wr(0xFF00 + self.fetch(), self.a); return 3
            if y == 6: self.a = self.rd(0xFF00 + self.fetch()); return 3
            d = self.fetch(); d = d - 256 if d > 127 else d
            sp = self.sp; r = (sp + d) & 0xFFFF
            self.flag(0, 0, (sp & 0xF) + (d & 0xF) > 0xF, (sp & 0xFF) + (d & 0xFF) > 0xFF)
            if y == 5: self.sp = r; return 4
            self.hl = r; return 3
        if z == 1:
            if q == 0:
                v = self.pop()
                if p == 0: self.bc = v
                elif p == 1: self.de = v
                elif p == 2: self.hl = v
                else: self.af = v
                return 3
            if p == 0: self.pc = self.pop(); return 4
            if p == 1: self.pc = self.pop(); self.ime = True; return 4
            if p == 2: self.pc = self.hl; return 1
            self.sp = self.hl; return 2
        if z == 2:
            if y < 4:
                a = self.fetch16()
                if self.cond(y): self.pc = a; return 4
                return 3
            if y == 4: self.wr(0xFF00 + self.c, self.a); return 2
            if y == 6: self.a = self.rd(0xFF00 + self.c); return 2
            a = self.fetch16()
            if y == 5: self.wr(a, self.a)
            else: self.a = self.rd(a)
            return 4
        if z == 3:
            if y == 0: self.pc = self.fetch16(); return 4
            if y == 1: return self.cb()
            if y == 6: self.ime = False; self.ime_pending = False; return 1
            if y == 7: self.ime_pending = True; return 1
            raise RuntimeError(f"illegal opcode {op:02x} at {self.cur_pc:04x}")
        if z == 4:
            a = self.fetch16()
            if y < 4 and self.cond(y): self.push(self.pc); self.pc = a; return 6
            if y < 4: return 3
            raise RuntimeError(f"illegal opcode {op:02x} at {self.cur_pc:04x}")
        if z == 5:
            if q == 0:
                self.push((self.bc, self.de, self.hl, self.af)[p]); return 4
            if p == 0:
                a = self.fetch16(); self.push(self.pc); self.pc = a; return 6
            raise RuntimeError(f"illegal opcode {op:02x} at {self.cur_pc:04x}")
        if z == 6:
            self.alu(y, self.fetch()); return 2
        self.push(self.pc); self.pc = y * 8; return 4


def from_pyboy(pb, rom: bytes) -> CPU:
    """Build a CPU from a live PyBoy instance (registers + RAM + guessed ROM bank)."""
    cpu = CPU(rom)
    m = pb.memory
    for a in range(0x8000, 0x10000):
        if 0xA000 <= a < 0xC000:
            continue
        cpu.mem[a] = m[a]
    banked = bytes(m[0x4000 + i] for i in range(0x100))
    for b in range(1, len(rom) // 0x4000):
        if rom[b * 0x4000:b * 0x4000 + 0x100] == banked:
            cpu.bank = b
            break
    r = pb.register_file
    cpu.a, cpu.f = r.A, r.F & 0xF0
    cpu.b, cpu.c, cpu.d, cpu.e = r.B, r.C, r.D, r.E
    cpu.hl = r.HL
    cpu.sp, cpu.pc = r.SP, r.PC
    cpu.cycles = m[0xFF44] * 114
    return cpu
