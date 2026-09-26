import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

try:
    import yaml  # noqa: F401
except ImportError:  # pragma: no cover
    yaml = None

from ultima_rov_dx import game_layout as GL  # noqa: E402
from ultima_rov_dx import patch_builder, rom_utils  # noqa: E402

ROM = ROOT / "rom" / "Ultima - Runes of Virtue (USA).gb"


@unittest.skipIf(yaml is None, "pyyaml not installed; run via `uv run`")
class TablesTest(unittest.TestCase):
    def setUp(self):
        import build_dx
        self.inputs = build_dx.load_inputs()

    def test_tables_shapes(self):
        from ultima_rov_dx import dx_patch
        t = dx_patch.build_tables(self.inputs["palettes"], self.inputs["bg_categories"], self.inputs["obj_categories"])
        self.assertEqual((len(t.objpal), len(t.base_bg), len(t.base_obj)), (128, 64, 64))
        themes = 1 + len(self.inputs["bg_categories"].get("area_themes") or {})
        self.assertEqual((len(t.lut_title), len(t.lut_game), len(t.lut_logo), len(t.metapal)), (256, 256, 256, 128 * themes))
        self.assertEqual((len(t.area_theme), len(t.bg_themes)), (256, 64 * dx_patch.MAX_THEMES))
        self.assertTrue(all(v < 8 for v in t.metapal + t.objpal + t.lut_game + t.lut_title + t.lut_logo))
        self.assertTrue(all(v < themes for v in t.area_theme))
        self.assertEqual(t.bg_themes[:64], t.base_bg)

    def test_cavern_theme(self):
        from ultima_rov_dx import dx_patch
        t = dx_patch.build_tables(self.inputs["palettes"], self.inputs["bg_categories"], self.inputs["obj_categories"])
        self.assertEqual((t.area_theme[0x18], t.area_theme[0x19], t.area_theme[0x02], t.area_theme[0x00]), (1, 1, 0, 0))
        cav = t.bg_themes[64:128]
        floor = cav[0:2]  # palette 0 (ui) keeps its color 0; the others share the cave floor
        self.assertEqual({cav[p * 8:p * 8 + 2] for p in range(1, 8)}, {cav[8:10]})
        self.assertEqual(floor, t.base_bg[0:2])

    def test_area_in_two_themes_rejected(self):
        from ultima_rov_dx import dx_patch
        bg = dict(self.inputs["bg_categories"])
        bg["area_themes"] = {"a": {"areas": [5]}, "b": {"areas": [5]}}
        with self.assertRaises(dx_patch.PatchError):
            dx_patch.build_tables(self.inputs["palettes"], bg, self.inputs["obj_categories"])

    def test_duplicate_metatile_rejected(self):
        from ultima_rov_dx import dx_patch
        bg = dict(self.inputs["bg_categories"])
        bg["metatile_palettes"] = {"stone": [1], "wood": [1]}
        with self.assertRaises(dx_patch.PatchError):
            dx_patch.build_tables(self.inputs["palettes"], bg, self.inputs["obj_categories"])

    def test_unknown_palette_rejected(self):
        from ultima_rov_dx import dx_patch
        obj = dict(self.inputs["obj_categories"])
        obj["ids"] = {"nope": [2]}
        with self.assertRaises(dx_patch.PatchError):
            dx_patch.build_tables(self.inputs["palettes"], self.inputs["bg_categories"], obj)


@unittest.skipUnless(ROM.is_file() and yaml is not None, "original ROM not present")
class RealRomBuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import build_dx
        cls.original = ROM.read_bytes()
        cls.out = build_dx.build(cls.original, build_dx.load_inputs())

    def test_header(self):
        hdr = rom_utils.parse_header(self.out)
        self.assertEqual(len(self.out), 0x40000)
        self.assertEqual(self.out[0x143], 0x80)
        self.assertEqual(self.out[0x147], GL.CARTRIDGE_TYPE)
        self.assertEqual(self.out[0x148], GL.DX_ROM_SIZE_CODE)
        self.assertEqual(hdr["header_checksum"], hdr["header_checksum_calc"])
        self.assertEqual(hdr["global_checksum"], hdr["global_checksum_calc"])

    def test_only_expected_bytes_change(self):
        allowed = set(range(0x0003, 0x0038)) | set(range(0x0061, 0x0100)) | {0x143, 0x148, 0x14D, 0x14E, 0x14F}
        for h in GL.HOOKS:
            allowed |= set(range(h.offset, h.offset + len(h.preimage)))
        for bank, addr in GL.GAME_LCD_ON_SITES + GL.TITLE_LCD_ON_SITES:
            off = GL.file_offset(bank, addr)
            allowed |= {off, off + 1}
        changed = {i for i in range(len(self.original)) if self.original[i] != self.out[i]}
        self.assertEqual(changed - allowed, set())
        self.assertEqual(self.out[len(self.original):len(self.original) + 3][:1], b"\xf0")  # bank 8 starts with code

    def test_lcd_sites_use_rst(self):
        for bank, addr in GL.GAME_LCD_ON_SITES:
            off = GL.file_offset(bank, addr)
            self.assertEqual(self.out[off], 0xEF)
            mode = 0x00 if (bank, addr) in GL.MAP_LCD_ON_SITES else 0x40   # nop / ld b,b
            self.assertEqual(self.out[off + 1], mode)
        for bank, addr in GL.TITLE_LCD_ON_SITES:
            self.assertEqual(self.out[GL.file_offset(bank, addr)], 0xF7)

    def test_ips_roundtrip(self):
        ips = patch_builder.build_ips_patch(self.original, self.out)
        self.assertEqual(patch_builder.apply_ips_patch(self.original, ips), self.out)

    def test_boots_in_color(self):
        try:
            from pyboy import PyBoy
        except ImportError:
            self.skipTest("pyboy not installed (uv sync --extra emu)")
        import tempfile
        import numpy as np
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as d:
            rom = Path(d) / "dx.gbc"
            rom.write_bytes(self.out)
            pb = PyBoy(str(rom), window="null", cgb=True, sound_emulated=False)
            pb.set_emulation_speed(0)
            pb.tick(520, True)
            px = np.array(pb.screen.image.convert("RGB")).astype(int)
            pb.stop(save=False)
        chroma = (px.max(axis=2) - px.min(axis=2))
        self.assertGreater((chroma > 40).mean(), 0.2, "title screen should be clearly colored")


if __name__ == "__main__":
    unittest.main()
