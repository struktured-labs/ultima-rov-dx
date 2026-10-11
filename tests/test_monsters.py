"""Monster templates, variant tiers and their run-time colours (notes/monsters.md)."""
import io
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

from ultima_rov_dx import game_layout as GL  # noqa: E402
from ultima_rov_dx import monsters as M  # noqa: E402

ROM = ROOT / "rom" / "Ultima - Runes of Virtue (USA).gb"


def _T(u, gfx, hp, dmg):
    return M.Template(u, 1, gfx, 0, hp, 0, dmg)


class TierRuleTest(unittest.TestCase):
    def test_synthetic(self):
        temps = [_T(0, 0x0C, 64, 8), _T(1, 0x0C, 48, 16),             # slime: damage doubles -> tier 1
                 _T(2, 0x0A, 8, 8), _T(3, 0x0A, 80, 0x80),            # bat + talker: one tier
                 _T(4, 0x22, 32, 1), _T(5, 0x22, 64, 1), _T(6, 0x22, 32, 15), _T(7, 0x22, 32, 25),
                 _T(8, 0x22, 48, 2), _T(9, 0x10, 1, 7), _T(10, 0x32, 8, 8), _T(11, 0x32, 72, 8),
                 _T(12, 0x40, 99, 30)]                               # not in tiered_keys
        t = M.tiers(temps, {0x0C, 0x0A, 0x22, 0x10, 0x32})
        self.assertEqual([t[i] for i in range(13)], [0, 1, 0, 0, 0, 0, 1, 2, 0, 0, 0, 1, 0])

    def test_table_packing(self):
        temps = [_T(i, 0, 8, 8) for i in range(5)]
        tab = M.tier_table(temps, {0: 1, 1: 2, 2: 0, 3: 1, 4: 2})
        self.assertEqual(tab, bytes([0x21, 0x10, 0x02]))


@unittest.skipUnless(ROM.is_file() and yaml is not None, "original ROM not present")
class RomTemplatesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = ROM.read_bytes()
        cls.temps = M.templates(cls.rom)
        cls.pal = yaml.safe_load((ROOT / "palettes" / "rov_palettes.yaml").read_text())
        cls.cats = yaml.safe_load((ROOT / "palettes" / "obj_categories.yaml").read_text())
        cls.ckeys = {k for c in cls.pal["creatures"].values() for k in c["ids"]}
        cls.tier = M.tiers(cls.temps, cls.ckeys)
        cls.by_name = {t.name: t for t in cls.temps}

    def tier_of(self, name):
        return self.tier[self.by_name[name].index]

    def test_template_table(self):
        self.assertEqual(len(self.temps), 139)
        self.assertEqual(M.TEMPLATE_ADDR + 9 * M.NORMAL_TYPES, 0x580A)   # the spawner's alt table
        s, b = self.by_name["A02"], self.by_name["B11"]                  # green and red slimes
        self.assertEqual((s.key, s.hp, s.damage), (0x0C, 64, 8))
        self.assertEqual((b.key, b.hp, b.damage), (0x0C, 48, 16))

    def test_variants_get_tiers(self):
        for name, tier in (("A02", 0), ("B11", 1), ("A05", 0), ("A08", 1), ("A10", 0), ("B10", 1),
                           ("A24", 0), ("A1E", 0), ("B1D", 1), ("B17", 1), ("B16", 2), ("A12", 2),
                           ("B09", 0), ("A14", 1), ("B21", 0), ("B15", 1), ("A04", 0), ("A3A", 1),
                           ("A01", 0), ("A00", 0), ("A3B", 0), ("A2B", 0), ("A15", 0)):
            self.assertEqual(self.tier_of(name), tier, name)

    def test_single_stat_types_one_colour(self):
        for key in (0x0A, 0x14, 0x16, 0x04, 0x2A, 0x34, 0x28):           # bats, rats, spider...
            self.assertEqual({self.tier[t.index] for t in self.temps if t.key == key and not t.gfx & 0x40},
                             {0}, hex(key))

    def test_no_per_area_obj_tint(self):
        # one natural colour per creature everywhere; variants only where the ROM has tougher templates
        self.assertFalse(self.pal.get("obj_themes"))
        self.assertNotIn("tier_palettes", self.cats)
        for name, c in self.pal["creatures"].items():
            found = {self.tier[t.index] for t in self.temps if t.key in c["ids"]}
            self.assertEqual(max(found | {0}), len(c.get("variants") or []), name)

    def test_tier_table_in_rom(self):
        import build_dx
        from ultima_rov_dx import dx_patch
        from ultima_rov_dx.sm83asm import assemble
        out = build_dx.build(self.rom, build_dx.load_inputs())
        _, syms = assemble([("dx.asm", dx_patch._asm_source())])
        off = GL.file_offset(2, syms["TIER_TAB"])
        from ultima_rov_dx import creatures as CR
        cr = CR.build(self.pal, self.cats, self.temps)
        self.assertEqual(set(cr.tiered_keys), {0x0C, 0x0E, 0x1A, 0x1C, 0x1E, 0x20, 0x22, 0x24, 0x26, 0x2C, 0x32})
        tab = M.tier_table(self.temps, M.tiers(self.temps, set(cr.tiered_keys)))
        self.assertEqual(tab, M.tier_table(self.temps, self.tier))         # untiered creatures: tier 0 anyway
        self.assertEqual(out[off:off + len(tab)], tab)
        self.assertEqual(set(self.rom[GL.BANK2_FREE[0]:GL.BANK2_FREE[1]]), {0xFF})   # was unused fill
        alloc = GL.file_offset(2, 0x5FE6)
        self.assertEqual(self.rom[alloc:alloc + 3], b"\x01\x00\xd0")              # ld bc,$D000
        self.assertEqual(out[alloc], 0xC3)                                         # jp AllocHook


@unittest.skipUnless(ROM.is_file() and yaml is not None, "original ROM not present")
class RuntimeColoursTest(unittest.TestCase):
    """Teleport into areas with mixed variants: each creature OAM entry uses the palette the
    natural-colour allocation (creatures.allocate on the live state) gives its class, plus its
    template's tier where the creature owns a block of tier palettes; floor-item tiles use their
    item's palette."""

    def test_variant_and_pickup_palettes(self):
        try:
            from pyboy import PyBoy
        except ImportError:
            self.skipTest("pyboy not installed (uv sync --extra emu)")
        import build_dx
        import capture_screens as cs
        from ultima_rov_dx import creatures as CR, dx_patch
        from ultima_rov_dx.sm83asm import assemble
        inp = build_dx.load_inputs()
        out = build_dx.build(ROM.read_bytes(), inp)
        cr = CR.build(inp["palettes"], inp["obj_categories"], M.templates(ROM.read_bytes()))
        _, syms = assemble([("dx.asm", dx_patch._asm_source())])
        rec_tier, lut, item_pal, lcd_mode = syms["REC_TIER"], syms["LUT"], syms["ITEM_PAL"], syms["LCD_MODE"]
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as d:
            rom = Path(d) / "dx.gbc"
            rom.write_bytes(out)
            pb = PyBoy(str(rom), window="null", cgb=True, sound_emulated=False)
            pb.set_emulation_speed(0)
            m = pb.memory
            hit = []
            pb.hook_register(3, cs.CHARACTER_SELECT_LCD_ON, lambda _c: hit.append(1), None)
            for _scene, actions in cs.ROUTE[:6]:
                for button, hold, after in actions:
                    if button == "until":
                        for _ in range(60):
                            pb.button_press(hold); pb.tick(6, True); pb.button_release(hold)
                            for _ in range(54):
                                pb.tick(1, True)
                                if hit:
                                    break
                            if hit:
                                break
                        pb.tick(54, True)
                        continue
                    if button:
                        pb.button_press(button); pb.tick(hold, True); pb.button_release(button)
                    pb.tick(max(after, 1), True)
            st = io.BytesIO()
            pb.save_state(st)

            def teleport(dest):
                for d in ("right", "left", "down", "up"):
                    st.seek(0); pb.load_state(st)
                    p = m[0xFF91]
                    nb = [(p + 1) & 0xFF, (p - 1) & 0xFF, (p + 16) & 0xFF, (p - 16) & 0xFF]
                    for i in range(16):                      # every warp of the room -> dest
                        m[0xC560 + 2 * i] = nb[i % 4]; m[0xC561 + 2 * i] = dest
                    m[1, 0xD13E] = 0
                    pb.button_press(d); pb.tick(20, True); pb.button_release(d)
                    for _ in range(400):
                        pb.tick(1, True)
                        if m[1, 0xD12F] == dest and m[0xFF40] & 0x80:
                            pb.tick(60, True)
                            return True
                return False

            seen = {}
            items = 0
            for area in (0x2C, 0x27, 0x4A):                  # trolls x3, skeletons x2, gremlins x2
                self.assertTrue(teleport(area), hex(area))
                for _ in range(400):                         # map attributes up (before any death)
                    if m[2, lcd_mode] == 0:
                        break
                    pb.tick(1, True)
                self.assertEqual(m[2, lcd_mode], 0, hex(area))
                for k in range(15):                          # floor pickups: their item's palette
                    i = m[0xC5B0 + k]
                    if i != 0xFF:
                        items += 1
                        self.assertEqual(m[2, lut + 0x40 + 4 * k], m[2, item_pal + (i & 0x3F)], f"{area:#x} slot {k}")
                pb.tick(180, True)                           # let the room's spawns settle
                bad = good = carried = 0
                pals = set()
                for _ in range(120):
                    pb.tick(1, True)
                    slots, n = [m[0xC580 + j] for j in range(16)], min(m[0xC539], 16)
                    lst, j = [], 0xC5C0
                    while j < 0xC600 and m[j + 1]:
                        lst.append((m[j], m[j + 1])); j += 2
                    al = CR.allocate(cr, slots, n, lst, m[0xC508], surface=m[2, syms["MAP_THEME"]] == 0)
                    for i in range(16):
                        if m[1, 0xD000 + 16 * i] == 0xFF:
                            continue
                        off = m[1, 0xD003 + 16 * i]
                        if not 0 < off < 0xA0:
                            continue
                        t = m[2, rec_tier + i]
                        for k in (0, 4):
                            y, tile, attr = m[0xFE00 + off + k], m[0xFE02 + off + k], m[0xFE03 + off + k]
                            s = (tile - 0x80) >> 3
                            if y == 0 or tile < 0x80 or s >= n or attr & 0x10:
                                continue
                            while s > 0 and slots[s] == 0xFF:
                                s -= 1
                            v = al.objpal[slots[s] & 0x7E]
                            want = (v & 7) + (t if v & 0x80 else 0)
                            at = attr & 7
                            pals.add((cr.names[cr.class_of_key(slots[s] & 0x7E) - 1], at - (v & 7)))
                            bad += at != want
                            good += at == want
                            carried += (m[0xC003 + off + k] & 7) == at   # coloured in the shadow OAM
                seen[area] = pals
                # Prep8 colours the shadow OAM at the game's idle wait (tiers rebuilt from the
                # records first), so no frame shows a monster in another tier's colour, and
                # the DMA itself carries the palettes on most frames
                self.assertGreater(good, 0, hex(area))
                self.assertEqual(bad, 0, hex(area))
                self.assertGreater(carried, good // 2, hex(area))
            pb.stop(save=False)
        self.assertGreater(items, 3)
        self.assertIn(("troll", 2), seen[0x2C])              # strongest trolls (B16): third palette of the block
        self.assertIn(("skeleton", 1), seen[0x27])           # 25-damage skeletons (the base one may be off screen)
        self.assertIn(("gremlin", 1), seen[0x4A])            # 64 HP / 23 damage gremlins


if __name__ == "__main__":
    unittest.main()
