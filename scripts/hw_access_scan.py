"""Hardware access scan: run a DX build in an instrumented SameBoy core and
count VRAM, CGB palette (BCPD/OCPD) and OAM writes that land while the PPU
blocks them (mode 3 / mode 2-3), per CPU speed and per PC.

Build the core first: tools/sameboy_harness/build.sh (sets up /tmp/sbh-build,
or point SBH_DIR at another directory).

Usage: uv run --extra emu python scripts/hw_access_scan.py ROM [TAG] [N_AREAS]
Route: boot to the throne room (capture_screens.ROUTE), then teleport into
up to 7 areas, wander, attack, open the start menu. Double speed is what DX
runs in; patch the `stop` after the KEY1 write to NOPs for a single-speed run.
"""
import random, sys

import ctypes as C, numpy as np, collections
sys.path.insert(0, 'scripts')
import capture_screens as cs
import os
W = os.environ.get('SBH_DIR', '/tmp/sbh-build')
L = C.CDLL(os.path.join(W, 'libsbh.so'))
BOOT = os.path.join(W, 'cgb_boot.bin').encode()
class EV(C.Structure):
    _fields_ = [('pc', C.c_uint16), ('addr', C.c_uint16), ('bank', C.c_uint8), ('val', C.c_uint8), ('ly', C.c_uint8),
                ('mode', C.c_uint8), ('ds', C.c_uint8), ('lcdc', C.c_uint8), ('kind', C.c_uint8), ('blocked', C.c_uint8)]
L.sb_open.restype = C.c_void_p; L.sb_open.argtypes = [C.c_char_p, C.c_char_p]
for f in ('sb_frame', 'sb_read', 'sb_write', 'sb_svbk', 'sb_state_size', 'sb_save', 'sb_load', 'sb_direct'):
    getattr(L, f).argtypes = None
L.sb_frame.argtypes = [C.c_void_p, C.c_int]
L.sb_read.argtypes = [C.c_void_p, C.c_uint16]; L.sb_read.restype = C.c_uint8
L.sb_write.argtypes = [C.c_void_p, C.c_uint16, C.c_uint8]
L.sb_direct.argtypes = [C.c_void_p, C.c_int, C.POINTER(C.c_size_t)]; L.sb_direct.restype = C.POINTER(C.c_uint8)
L.sb_events.argtypes = [C.POINTER(C.c_int)]; L.sb_events.restype = C.POINTER(EV)
L.sb_pixels.restype = C.POINTER(C.c_uint32)
for f in ('sb_hist', 'sb_blocked', 'sb_total'): getattr(L, f).restype = C.POINTER(C.c_uint32)
L.sb_state_size.argtypes = [C.c_void_p]; L.sb_state_size.restype = C.c_size_t
L.sb_save.argtypes = [C.c_void_p, C.c_char_p]; L.sb_load.argtypes = [C.c_void_p, C.c_char_p, C.c_size_t]
KEY = {'right': 1, 'left': 2, 'up': 4, 'down': 8, 'a': 16, 'b': 32, 'select': 64, 'start': 128}
KIND = ['VRAM', 'BGPD', 'OBPD', 'OAM', 'REG']
class SB:
    def __init__(s, rom):
        s.g = L.sb_open(rom.encode(), BOOT); assert s.g
        n = C.c_size_t(); s.ram = np.ctypeslib.as_array(L.sb_direct(s.g, 1, C.byref(n)), (n.value,))
        s.ev = collections.Counter(); s.blk = collections.Counter(); s.frames = 0
        s.hist = np.zeros((4, 2, 154), np.int64); s.blocked = np.zeros((4, 2), np.int64); s.total = np.zeros((4, 2), np.int64)
        s.blocked_ev = []; s.regs = []
    def drain(s):
        n = C.c_int(); e = L.sb_events(C.byref(n))
        for i in range(n.value):
            x = e[i]
            if x.kind == 4: s.regs.append((s.frames, x.addr, x.val, x.ly, x.ds, x.lcdc)); continue
            key = (KIND[x.kind], x.bank if x.pc >= 0x4000 else 0, x.pc, x.ds)
            if x.blocked:
                s.blk[key] += 1
                if s.blk[key] <= 4: s.blocked_ev.append((s.frames, KIND[x.kind], hex(x.addr), x.bank, hex(x.pc), x.ly, x.mode, x.ds))
            else: s.ev[key + (x.mode,)] += 1
        s.hist += np.ctypeslib.as_array(L.sb_hist(), (4, 2, 154)); s.blocked += np.ctypeslib.as_array(L.sb_blocked(), (4, 2))
        s.total += np.ctypeslib.as_array(L.sb_total(), (4, 2)); L.sb_clear()
    def run(s, n=1, keys=()):
        m = sum(KEY[k] for k in keys)
        for _ in range(n):
            L.sb_frame(s.g, m); s.frames += 1
            if s.frames % 8 == 0: s.drain()
    def frame(s):
        a = np.ctypeslib.as_array(L.sb_pixels(), (144, 160)).copy()
        return np.stack([(a >> 16) & 255, (a >> 8) & 255, a & 255], -1).astype(np.uint8)
    def w1(s, addr, bank=1): return int(s.ram[bank * 0x1000 + addr - 0xD000])
    def setw1(s, addr, v, bank=1): s.ram[bank * 0x1000 + addr - 0xD000] = v
    def save(s):
        b = C.create_string_buffer(L.sb_state_size(s.g)); L.sb_save(s.g, b); return b
    def load(s, b): assert L.sb_load(s.g, b, len(b)) == 0
def q5(a): return a.astype(int) >> 3
def binz(a):
    l = a.astype(int).sum(-1); return l > (l.min() + l.max()) / 2
def boot(s):
    """capture_screens.ROUTE; `until` = character select (LCD_BYTE $7F, LCD_MODE 2 in WRAM2)."""
    for scene, actions in cs.ROUTE:
        for button, hold, after in actions:
            if button == 'until':
                for _ in range(12):
                    s.run(6, [hold]); s.run(54)
                    if s.w1(0xD706, 2) == 0x7F and s.w1(0xD703, 2) == 2:
                        break
                else:
                    raise SystemExit('character select not reached')
                continue
            if button: s.run(hold, [button])
            s.run(max(after, 1))
def teleport(s, st, dest, flag=None):
    for d in ('right', 'left', 'down', 'up'):
        s.load(st)
        p = L.sb_read(s.g, 0xFF91)
        nb = [(p + 1) & 0xFF, (p - 1) & 0xFF, (p + 16) & 0xFF, (p - 16) & 0xFF]
        for i in range(16):
            L.sb_write(s.g, 0xC560 + 2 * i, nb[i % 4]); L.sb_write(s.g, 0xC561 + 2 * i, dest)
        if flag is not None: s.setw1(0xD13E, flag)
        s.run(20, [d])
        for _ in range(400):
            s.run(1)
            if s.w1(0xD12F) == dest and L.sb_read(s.g, 0xFF40) & 0x80: break
        if s.w1(0xD12F) == dest: s.run(120); return True
    return False


if __name__ == '__main__':
    rom, tag = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else 'scan')
    AREAS = [(0x2C, None), (0x27, None), (0x4A, None), (0x3D, None), (0x49, None), (0x4C, None), (0x00, None)]
    if len(sys.argv) > 3: AREAS = AREAS[:int(sys.argv[3])]
    s = SB(rom); boot(s)
    st = s.save(); rnd = random.Random(1)
    shots = {}
    for dest, flag in AREAS:
        ok = teleport(s, st, dest, flag)
        if not ok: print('teleport fail', hex(dest)); continue
        for i in range(30):   # wander + attack
            s.run(rnd.randint(8, 30), [rnd.choice(['up', 'down', 'left', 'right'])])
            if i % 5 == 0: s.run(6, ['a']); s.run(10)
            if i % 7 == 0: s.run(6, ['b']); s.run(10)
        s.run(6, ['start']); s.run(90)
        s.run(6, ['right']); s.run(30); s.run(6, ['start']); s.run(90)
    s.drain()
    print('frames', s.frames)
    for k in range(4):
        for ds in range(2):
            if s.total[k, ds]: print(f'{KIND[k]:5s} ds={ds} writes(LCD on)={s.total[k,ds]:8d} blocked={s.blocked[k,ds]}')
    print('blocked samples (frame,kind,addr,bank,pc,ly,mode,ds):'); [print('  ', e) for e in s.blocked_ev[:40]]
    print('blocked by pc', s.blk.most_common(20))
    vis = collections.Counter()
    for (kind, bank, pc, ds, mode), n in s.ev.items(): vis[(kind, bank, hex(pc), ds, mode)] += n
    print('unblocked writes on visible lines (kind,bank,pc,ds,mode):', vis.most_common(25))
    spd = [r for r in s.regs if r[1] == 0xFF4D]; print('KEY1 writes', spd[:5], 'HDMA writes', sum(1 for r in s.regs if r[1] == 0xFF55))
