"""Natural creature colours: the table, the per-area allocation model and the bank-9
runtime run in the SM83 interpreter against that model (notes/monsters.md "Colours")."""
import copy
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

from ultima_rov_dx import creatures as CR  # noqa: E402
from ultima_rov_dx import game_layout as GL  # noqa: E402
from ultima_rov_dx import monsters as M  # noqa: E402

ROM = ROOT / "rom" / "Ultima - Runes of Virtue (USA).gb"


def _inputs():
    load = lambda n: yaml.safe_load((ROOT / "palettes" / n).read_text())  # noqa: E731
    return load("rov_palettes.yaml"), load("obj_categories.yaml")


@unittest.skipUnless(ROM.is_file() and yaml is not None, "original ROM not present")
class CreatureTableTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pal, cls.cat = _inputs()
        cls.temps = M.templates(ROM.read_bytes())
        cls.cr = CR.build(cls.pal, cls.cat, cls.temps)

    def test_one_colour_per_creature(self):
        cr = self.cr
        for name, ent in self.pal["creatures"].items():
            for k in ent["ids"]:
                self.assertEqual(cr.names[cr.class_of_key(k) - 1], name, hex(k))
            self.assertEqual(cr.class_tiers[cr.cls(name)], 1 + len(ent.get("variants") or []), name)
            self.assertTrue(ent.get("why"), f"{name}: rationale missing")
        self.assertEqual(cr.names[cr.folk - 1], "folk")
        generic = {cr.cls(n) for n, e in self.pal["npcs"].items() if e.get("variants")}   # $46 / $6A: folk
        cols = {cr.class_col[8 * c:8 * c + 8] for c in range(1, len(cr.names) + 1) if c not in generic}
        self.assertEqual(len(cols), len(cr.names) - len(generic))     # every class its own colours
        for c in generic:
            self.assertEqual(cr.class_col[8 * c:8 * c + 8], cr.class_col[8 * cr.folk:8 * cr.folk + 8])

    def test_variants_only_where_rom_has_tougher_templates(self):
        tiered = {n for n, e in self.pal["creatures"].items() if e.get("variants")}
        self.assertEqual(tiered, {"slime", "gremlin", "skeleton", "jagger", "troll", "snake", "centipede"})
        self.assertEqual(len(self.pal["creatures"]["troll"]["variants"]), 2)
        b11 = next(t for t in self.temps if t.name == "B11")              # red slime: tier 1
        self.assertEqual(self.cr.tpl[b11.index], 1 << 6 | self.cr.cls("slime"))

    def test_validation(self):
        for mutate in (lambda p, c: p["creatures"]["rat"]["ids"].append(0x0A),                 # duplicate id
                       lambda p, c: p["creatures"]["rat"].update(variants=[{"colors": ["#FFFFFF"] * 4}]),  # no ROM tier
                       lambda p, c: p["creatures"]["troll"]["variants"].pop(),                   # ROM has 3 tiers
                       lambda p, c: p.update(obj_themes={"cavern": {}}),
                       lambda p, c: c.update(tier_palettes=["creature_a"]),
                       lambda p, c: c["ids"]["folk"].append(0x14)):                             # rat in folk too
            p, c = copy.deepcopy(self.pal), copy.deepcopy(self.cat)
            mutate(p, c)
            with self.assertRaises(CR.CreatureError):
                CR.build(p, c, self.temps)

    def test_allocation(self):
        cr = self.cr
        troll, bat, rat, folk = (cr.cls(n) for n in ("troll", "bat", "rat", "folk"))
        b16 = next(t for t in self.temps if t.name == "B16")               # strongest troll (alt group)
        a = CR.allocate(cr, [0x0A, 0xA2, 0xFF, 0x14], 4, [(0x10, 0x80 | (b16.index - M.NORMAL_TYPES))], c508=0xC0)
        self.assertEqual((a.pal[bat], a.pal[troll], a.size[troll], a.pal[rat]), (1, 2, 3, 5))
        self.assertEqual((a.objpal[0x22], a.objpal[0x0A]), (0x82, 1))
        self.assertEqual(a.colors[4], cr.class_col[8 * (troll + 2):8 * (troll + 3)])
        a = CR.allocate(cr, [0x14], 1, surface=True)                      # ship: folk palette on the surface
        self.assertEqual((a.pal[rat], a.ship_pal), (1, 2))
        # seven classes: the last shares its nearest-coloured loaded class; variants merged first
        ids = [0x14, 0x0A, 0x16, 0x04, 0x2A, 0x28, 0x10]
        a = CR.allocate(cr, ids, 7)
        self.assertEqual(len(a.shared), 1)
        last = cr.class_of_key(0x10)
        self.assertIn(a.pal[last], range(1, 7))
        self.assertEqual(sorted(a.colors), [1, 2, 3, 4, 5, 6])

    def test_parade_plan(self):
        plan = CR.parade_plan(self.cr, GL.PARADE_LIST_BYTES)
        self.assertEqual(len(plan.pages), 5)
        self.assertLessEqual(set(plan.loads[0]), set(range(1, 7)))      # first page via BASE_OBJ at LCD-on
        for k in range(1, 5):                                            # preloaded while page k-1 is up
            self.assertFalse(set(plan.loads[k]) & set(plan.pages[k - 1].values()), k)
        for k, page in enumerate(plan.pages):
            self.assertEqual(len(set(page.values())), len(page))        # one palette per class
        self.assertEqual(plan.loads[1], [5, 6, 7])                        # Lord British stays, 3 new friends
        self.assertEqual(plan.pages[0], {"royal": 1, "sherry": 2, "chuckles": 3, "dr_cat": 4})
        self.assertEqual(plan.pages[1], {"royal": 1, "beh_lem": 5, "ariana": 6, "kador": 7})

    def test_npcs(self):
        # named NPCs: own map colours (with a why); shared graphics by template; generic folk unchanged
        cr, pal = self.cr, self.pal
        for name, ent in pal["npcs"].items():
            self.assertTrue(ent.get("why"), name)
            for k in ent["ids"]:
                self.assertEqual(cr.names[cr.class_of_key(k) - 1], name, hex(k))
                self.assertTrue(cr.npc[cr.class_of_key(k)], name)
                self.assertNotIn(k, self.cat["ids"]["folk"])
            for v in ent.get("variants") or []:
                self.assertTrue(v.get("why"), v["name"])
                c = cr.alias[v["name"]]
                self.assertTrue(cr.npc[c])
                for tn in v["templates"]:
                    t = next(t for t in self.temps if t.name == tn)
                    self.assertEqual(cr.tpl[t.index], (c - cr.class_of_key(t.key)) << 6 | cr.class_of_key(t.key), tn)
        self.assertEqual(sorted(cr.alias), sorted(
            ["sherry", "kador", "utomo", "finn", "ariana", "dr_cat", "beh_lem", "klip_klop", "chuckles", "hooded",
             "penumbra", "taynith", "melissa", "townsman", "johann", "loubet", "zoltan"]))
        for n in ("folk", "royal", "item", "troll", "rat"):
            self.assertFalse(cr.npc[cr.cls(n)], n)
        for k in (0x42, 0x44, 0x4A, 0x6E):                              # unnamed townsfolk
            self.assertEqual(cr.class_of_key(k), cr.folk, hex(k))
        for k in (0x48, 0x4C, 0x50, 0x56):                              # royals and guards unchanged
            self.assertEqual(cr.class_of_key(k), cr.cls("royal"), hex(k))
        for c in range(1, len(cr.names) + 1):                           # NPCs fall back to folk brown first
            if cr.npc[c] and cr.class_tiers[c]:
                self.assertEqual(cr.fallback[CR.FALLBACKS * c], cr.folk, cr.names[c - 1])
        t = {t.name: t for t in self.temps}
        self.assertEqual(cr.tiers[t["B3F"].index], 1)                   # Penumbra
        self.assertEqual(cr.tiers[t["B46"].index], 3)                   # Melissa
        self.assertEqual(cr.tiers.get(t["A23"].index, 0), 0)            # generic hooded figure: folk
        self.assertEqual(cr.tiers[t["B47"].index], 3)                   # Zoltan

    def test_npc_allocation(self):
        cr = self.cr
        cls = cr.cls
        # castle: Lord British (royal) + Chuckles: both fit
        a = CR.allocate(cr, [0x4C, 0x70], 2)
        self.assertEqual((a.pal[cls("royal")], a.pal[cls("chuckles")]), (1, 2))
        # NPC listed first still goes after the creatures
        a = CR.allocate(cr, [0x5C, 0x0A], 2)
        self.assertEqual((a.pal[cls("bat")], a.pal[cls("dr_cat")]), (1, 2))
        # town 01: item, Sherry, hooded (Penumbra), Gnu Gnu, Dr Cat, townsman (Johann B2A, Loubet B41)
        b = {t.name: t for t in self.temps}
        lst = [(0x10, 0x80 | b["B3F"].index - M.NORMAL_TYPES), (0x20, 0x80 | b["B2A"].index - M.NORMAL_TYPES),
               (0x30, 0x80 | b["B41"].index - M.NORMAL_TYPES)]
        a = CR.allocate(cr, [0x3A, 0x40, 0x46, 0x56, 0x5C, 0x6A], 6, lst, c508=0xC0)
        self.assertEqual(sorted(a.colors), [1, 2, 3, 4, 5, 6])
        self.assertFalse(a.shared)
        # seven: creatures, royal, item first; folk goes in before the NPCs; the NPC left over wears folk
        a = CR.allocate(cr, [0x40, 0x0A, 0x14, 0x16, 0x4C, 0x08, 0x5C], 7)
        self.assertEqual(a.pal[cls("folk")], 6)
        self.assertEqual((a.pal[cls("sherry")], a.pal[cls("dr_cat")]), (6, 6))
        self.assertEqual((a.objpal[0x40], a.objpal[0x5C]), (6, 6))
        for n in ("bat", "rat", "spider", "royal", "item"):
            self.assertIn(a.pal[cls(n)], range(1, 6), n)
        # generic folk already loaded: NPCs past palette 6 share it
        a = CR.allocate(cr, [0x42, 0x0A, 0x14, 0x16, 0x4C, 0x08, 0x5C], 7)
        self.assertEqual(a.pal[cls("dr_cat")], a.pal[cls("folk")])


class BankedCPU:
    """probes.sm83.CPU in double speed with CGB WRAM banking ($D000-$DFFF by SVBK) and CRAM capture."""

    def __new__(cls, rom):
        from probes.sm83 import CPU

        class _C(CPU):
            def __init__(self, rom):
                super().__init__(rom)
                self.wram = {b: bytearray(0x1000) for b in range(1, 8)}
                self.svbk = 2
                self.cram = bytearray(64)
                self.ocps = 0
                self.ocpd_writes = []

            def ly(self):                     # DX runs the CPU in double speed: 228 M-cycles a line
                return (self.cycles // 228) % 154

            def rd(self, addr):
                addr &= 0xFFFF
                if 0xD000 <= addr < 0xE000:
                    return self.wram[self.svbk][addr - 0xD000]
                if addr == 0xFF70:
                    return self.svbk
                return super().rd(addr)

            def wr(self, addr, val):
                addr &= 0xFFFF
                val &= 0xFF
                if 0xD000 <= addr < 0xE000:
                    for lo, hi, cb in self.write_watch:
                        if lo <= addr < hi:
                            cb(self, addr, val)
                    self.wram[self.svbk][addr - 0xD000] = val
                    return
                if addr == 0xFF70:
                    self.svbk = (val & 7) or 1
                elif addr == 0xFF6A:
                    self.ocps = val
                elif addr == 0xFF6B:
                    i = self.ocps & 0x3F
                    self.cram[i] = val
                    self.ocpd_writes.append((i, self.ly()))
                    if self.ocps & 0x80:
                        self.ocps = 0x80 | ((i + 1) & 0x3F)
                super().wr(addr, val)
        return _C(rom)


@unittest.skipUnless(ROM.is_file() and yaml is not None, "original ROM not present")
class NaturalRuntimeTest(unittest.TestCase):
    """Bank-9 NatLcd9 / NatPrep9, bank-8 SyncDirty8 and the parade preload, interpreted."""

    @classmethod
    def setUpClass(cls):
        import build_dx
        from ultima_rov_dx import dx_patch
        from ultima_rov_dx.sm83asm import assemble
        cls.original = ROM.read_bytes()
        inp = build_dx.load_inputs()
        cls.out = build_dx.build(cls.original, inp)
        _, cls.S = assemble([("dx.asm", dx_patch._asm_source())])
        cls.temps = M.templates(cls.original)
        cls.cr = CR.build(inp["palettes"], inp["obj_categories"], cls.temps)
        cls.plan = dx_patch.parade_plan(cls.original, cls.cr)

    def cpu(self):
        S = self.S
        c = BankedCPU(self.out)
        c.ime = False
        b8 = GL.file_offset(8, 0x4000)
        img = b8 + S["W2_IMAGE_ROM"] - 0x4000
        c.wram[2][:] = self.out[img:img + 0x1000]
        c.mem[0xC5C0 + 1] = 0                                          # empty area list
        return c

    def call(self, c, entry, bank, a=0, b=0, limit=200000):
        c.bank = bank
        c.sp, c.pc, c.a, c.b = 0xCFF0, entry, a, b
        c.push(0x0000)
        start = c.cycles
        for _ in range(limit):
            if c.pc == 0x0000:
                return c.cycles - start
            c.step()
        self.fail(f"{entry:#x} did not return")

    def w2(self, c, addr, n=1):
        return bytes(c.wram[2][addr - 0xD000:addr - 0xD000 + n])

    def scene(self, c, slots, lst=(), c508=0xFF, surface=False, area=0x10):
        S = self.S
        c.mem[S["SPRITE_COUNT"]] = len(slots)
        c.mem[0xC580:0xC590] = bytes(list(slots) + [0] * (16 - len(slots)))
        c.mem[0xC5C0:0xC600] = bytes(0x40)
        for i, (pos, t) in enumerate(lst[:31]):
            c.mem[0xC5C0 + 2 * i:0xC5C2 + 2 * i] = bytes([pos, t])
        c.mem[S["AREA_ALT"]] = c508
        c.wram[1][S["AREA_ID"] - 0xD000] = area
        c.wram[2][S["MAP_THEME"] - 0xD000] = 0 if surface else 3
        return CR.allocate(self.cr, list(slots), len(slots), list(lst), c508, surface)

    def check(self, c, al, slots):
        S = self.S
        for p, col in al.colors.items():
            self.assertEqual(self.w2(c, S["BASE_OBJ"] + 8 * p, 8), col, f"palette {p}")
        for g in slots[:16]:
            if g != 0xFF:
                k = g & 0x7E
                self.assertEqual(self.w2(c, S["OBJPAL"] + k, 2), bytes([al.objpal[k]] * 2), hex(k))
        if al.ship_pal:
            self.assertEqual(self.w2(c, S["SHIP_PAL"])[0], al.ship_pal)
        self.assertEqual(c.svbk, 2)

    def test_assign_matches_model(self):
        S, cr = self.S, self.cr
        rnd = random.Random(7)
        keys = sorted({k for k in range(0, 0x80, 2) if cr.class_of_key(k) != cr.cls("folk")} | {0x40, 0x48, 0x08})
        tiered = [t for t in self.temps if t.key in cr.tiered_keys and t.index < 2 * M.NORMAL_TYPES]
        c = self.cpu()
        worst = 0
        for n in range(300):
            cnt = rnd.randint(0, 16)
            slots = []
            while len(slots) < cnt:
                g = rnd.choice(keys) | rnd.choice((0, 0x80, 1))
                slots += [g] + [0xFF] * rnd.choice((0, 0, 1, 2))
            slots = slots[:16]
            c508 = rnd.choice((0xC4, 0xD0, 0xFF))
            lst = []
            for _ in range(rnd.randint(0, 12)):
                t = rnd.choice(tiered) if rnd.random() < 0.6 else rnd.choice(self.temps[:M.NORMAL_TYPES])
                pos = 0xC5C0 + 2 * len(lst)
                ty = t.index if t.index < M.NORMAL_TYPES else t.index - M.NORMAL_TYPES
                if ty >= CR.FLOOR_TYPES or ty == 0:
                    continue
                if (t.index >= M.NORMAL_TYPES) != ((pos & 0xFF) >= c508):
                    continue
                lst.append((rnd.randrange(256), 0x80 | ty))
            before = bytes(self.w2(c, S["BASE_OBJ"], 64))
            c.mem[S["NAT_DIRTY"]] = 0
            al = self.scene(c, slots, lst, c508, surface=rnd.random() < 0.3)
            worst = max(worst, self.call(c, S["NatLcd9"], 9))
            self.check(c, al, slots)
            after = self.w2(c, S["BASE_OBJ"], 64)
            dirty = sum(1 << p for p in range(8) if before[8 * p:8 * p + 8] != after[8 * p:8 * p + 8])
            self.assertEqual(c.mem[S["NAT_DIRTY"]], dirty, n)
        self.assertLess(worst, 7300)          # M-cycles (~32 lines): LCD-on, or NatPrep9 below NAT_LY only
        self.assertLessEqual(S["NAT_LY"] + 7300 // 228, 130)   # room left for OamPass before VBlank

    def test_prep_only_on_change_and_ly_guard(self):
        S = self.S
        c = self.cpu()
        slots = [0x22, 0xFF, 0xFF, 0x14]
        self.scene(c, slots)
        self.call(c, S["NatLcd9"], 9)
        c.mem[S["NAT_DIRTY"]] = 0
        c.cycles = 10 * 228
        cost = self.call(c, S["NatPrep9"], 9)                  # unchanged: signature check only
        self.assertEqual(c.mem[S["NAT_DIRTY"]], 0)
        self.assertLess(cost, 600)
        al = self.scene(c, [0x22, 0xFF, 0xFF, 0x0A])         # a bat replaces the rat
        c.cycles = 130 * 228                                  # late in the frame: wait
        self.call(c, S["NatPrep9"], 9)
        self.assertEqual(c.mem[S["NAT_DIRTY"]], 0)
        self.assertEqual(c.wram[3][S["NAT_SIG"] - 0xD000], 0xEE)
        c.cycles = 20 * 228
        self.call(c, S["NatPrep9"], 9)
        self.check(c, al, [0x22, 0xFF, 0xFF, 0x0A])
        self.assertEqual(c.mem[S["NAT_DIRTY"]], 1 << 2)        # only the bat's palette changed

    def test_sync_dirty_in_vblank_window(self):
        S = self.S
        c = self.cpu()
        al = self.scene(c, [0x0C, 0x14, 0x16])
        self.call(c, S["NatLcd9"], 9)
        c.mem[S["PARADE_ON"]] = 0
        c.mem[S["NAT_DIRTY"]] = 0b0000_0110
        c.wram[2][S["LAST_OBP0"] - 0xD000] = 0xE4
        c.cycles = 100 * 228
        self.call(c, S["SyncDirty8"], 8, b=self.out[0x4001])
        self.assertEqual((c.ocpd_writes, c.mem[S["NAT_DIRTY"]]), ([], 0b110))   # not in VBlank: kept
        c.cycles = 144 * 228
        cost = self.call(c, S["SyncDirty8"], 8, b=self.out[0x4001])
        self.assertEqual(c.mem[S["NAT_DIRTY"]], 0)
        self.assertEqual([i for i, _ in c.ocpd_writes], list(range(8, 24)))
        self.assertTrue(all(144 <= ly <= 145 for _, ly in c.ocpd_writes))
        self.assertEqual(bytes(c.cram[8:24]), al.colors[1] + al.colors[2])
        self.assertLess(cost, 600)          # two palettes; the window stops new ones past LY 145
        self.assertEqual(c.a, 1)                                                # SigBank: the caller's bank in A

    def test_parade_preload(self):
        # each page's colours are in CRAM before its graphics are loaded, and a
        # palette the page on screen uses is never written
        S, plan = self.S, self.plan
        c = self.cpu()
        lists = [S["PARADE_LISTS"] + 5 * k for k in range(5)]
        c.mem[S["PARADE_LIST"]] = lists[0] & 0xFF
        c.mem[S["PARADE_ON"]] = 1
        self.call(c, S["ParadePage9"], 9)
        c.mem[S["NAT_DIRTY"]] = 0                                               # ParadeOn8, then the LCD-on
        c.cram[:] = self.w2(c, S["BASE_OBJ"], 64)                               # SyncOBJ writes all of CRAM
        c.wram[2][S["LAST_OBP0"] - 0xD000] = 0xE4
        for k in range(5):
            c.mem[S["PARADE_LIST"]] = lists[k] & 0xFF
            for p in plan.pages[k].values():
                self.assertEqual(bytes(c.cram[8 * p:8 * p + 8]), plan.colors[64 * k + 8 * p:64 * k + 8 * p + 8], (k, p))
            shown = set(plan.pages[k].values())
            for f in range(12):                                                 # frames of page k
                c.ocpd_writes.clear()
                c.cycles = (154 * f + 146) * 228
                cost = self.call(c, S["SyncDirty8"], 8, b=self.out[0x4001])
                self.assertFalse({i // 8 for i, _ in c.ocpd_writes} & shown, (k, f))
                self.assertLess(cost, 800)          # one palette per frame, ~3 lines (SameBoy: no blocked writes)
        # after the last page's frames every page has been shown in its own colours
        self.assertEqual(c.mem[S["PARADE_CUR"]], lists[4] & 0xFF)


if __name__ == "__main__":
    unittest.main()
