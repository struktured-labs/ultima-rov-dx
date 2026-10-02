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
        self.assertLessEqual(themes, dx_patch.ROM_THEMES)
        self.assertEqual((len(t.lut_title), len(t.lut_game), len(t.lut_logo), len(t.metapal)),
                         (256, 256, 256, 128 * dx_patch.ROM_THEMES))
        self.assertEqual((len(t.area_theme), len(t.bg_themes)), (512, 64 * dx_patch.MAX_THEMES))
        self.assertEqual((len(t.theme_bg_rom), len(t.theme_obj_rom), len(t.rt_slot)),
                         (64 * dx_patch.ROM_THEMES, 8 * dx_patch.ROM_THEMES, dx_patch.ROM_THEMES))
        self.assertTrue(all(v < 8 for v in t.metapal + t.objpal + t.lut_game + t.lut_title + t.lut_logo))
        self.assertTrue(all(v < themes for v in t.area_theme))
        self.assertEqual(t.bg_themes[:64], t.base_bg)

    def test_cavern_theme(self):
        from ultima_rov_dx import dx_patch
        t = dx_patch.build_tables(self.inputs["palettes"], self.inputs["bg_categories"], self.inputs["obj_categories"])
        self.assertEqual((t.area_theme[0x18], t.area_theme[0x19], t.area_theme[0x02], t.area_theme[0x00]), (1, 1, 0, 0))
        cav = t.bg_themes[64:128]
        # all 8 palettes (side panel included) share the cave floor as colour 0
        self.assertEqual({cav[p * 8:p * 8 + 2] for p in range(8)}, {cav[8:10]})
        self.assertNotEqual(cav[8:10], t.base_bg[8:10])

    def test_menu_tables(self):
        from ultima_rov_dx import dx_patch
        t = dx_patch.build_tables(self.inputs["palettes"], self.inputs["bg_categories"], self.inputs["obj_categories"])
        bg = self.inputs["bg_categories"]
        names = list(bg["area_themes"])
        pal = list(self.inputs["palettes"]["bg_palettes"])
        self.assertEqual(t.ui_theme, dx_patch.SLOT_UI)
        self.assertEqual(t.rt_slot[1 + names.index(bg["ui_theme"])], dx_patch.SLOT_UI)
        self.assertEqual((len(t.lut_menu), len(t.item_pal), len(t.menu_obj)), (256, 64, 8))
        self.assertTrue(all(v < 8 for v in t.lut_menu + t.item_pal))
        # coin gold, heart red, bow wood, rope (item $2C) not the plain ui palette
        self.assertEqual(t.item_pal[0x09], pal.index("gold"))
        self.assertEqual(t.item_pal[0x10], pal.index("fire"))
        self.assertEqual(t.item_pal[0x01], pal.index("wood"))
        self.assertGreaterEqual(len(set(t.item_pal)), 6)
        # side-panel glyphs: hearts red, stars / coin / A: B: gold (map and menu)
        # (on the map, hearts use the panel palette 0 whose shade 2 is red)
        self.assertEqual((t.lut_game[0xF4], t.lut_menu[0xF4]), (pal.index("ui"), pal.index("fire")))
        for lut in (t.lut_game, t.lut_menu):
            self.assertEqual({lut[i] for i in (0xE4, 0xF5, 0xF7)}, {pal.index("gold")})
        self.assertEqual({t.lut_game[0xF2], t.lut_game[0xF3]}, {pal.index("gold")})
        # menu theme: one shared paper colour 0 behind every palette
        menu = t.bg_themes[64 * t.ui_theme:64 * (t.ui_theme + 1)]
        self.assertEqual(len({menu[p * 8:p * 8 + 2] for p in range(8)}), 1)

    def test_item_in_two_palettes_rejected(self):
        from ultima_rov_dx import dx_patch
        bg = dict(self.inputs["bg_categories"])
        bg["item_palettes"] = {"gold": [9], "fire": [9]}
        with self.assertRaises(dx_patch.PatchError):
            dx_patch.build_tables(self.inputs["palettes"], bg, self.inputs["obj_categories"])

    def test_entrance_scene_tables(self):
        from ultima_rov_dx import dx_patch
        t = dx_patch.build_tables(self.inputs["palettes"], self.inputs["bg_categories"], self.inputs["obj_categories"])
        names = list(self.inputs["bg_categories"]["area_themes"])
        self.assertEqual(t.entrance_theme, dx_patch.SLOT_ENTRANCE)
        self.assertEqual(t.rt_slot[1 + names.index("entrance")], dx_patch.SLOT_ENTRANCE)
        self.assertEqual(len(t.picture_lut), 256)
        self.assertTrue(all(v < 8 for v in t.picture_lut))
        # the cutscene uses several palettes (cliff, sky, mountains, plain, ground)
        self.assertGreaterEqual(len(set(t.picture_lut[:0xE4])), 5)
        self.assertEqual(len(t.flat_bg), 8)
        self.assertEqual(t.flat_bg[:2], b"\xff\x7f")   # blank screens are white
        ent = t.bg_themes[64 * t.entrance_theme:64 * (t.entrance_theme + 1)]
        # picture palettes 1-7 share colours 2 and 3 (cliff, rocks): no seams between regions
        self.assertEqual(len({ent[p * 8 + 4:p * 8 + 8] for p in range(1, 8)}), 1)
        fix = t.picture_fix
        self.assertEqual((fix[-2:], len(fix) % 3), (b"\0\0", 2))
        cells = {fix[i] | fix[i + 1] << 8: fix[i + 2] for i in range(0, len(fix) - 2, 3)}
        self.assertEqual(cells[0x9800 + 13 * 32 + 19], t.picture_lut[0x70])   # $1E at the ground edge

    # one representative level per dungeon, (area id, $D13E flag)
    DUNGEONS = {
        "cavern": [(0x18, 0), (0x28, 0)], "deceit": [(0x12, 0), (0x2F, 0)],
        "cowardice": [(0x06, 0), (0x11, 0)], "injustice": [(0x00, 1), (0x13, 1)],
        "dishonor": [(0x14, 1), (0x28, 1)], "selfishness": [(0x34, 0), (0x45, 0), (0x4D, 0)],
        "pride": [(0x29, 1), (0x43, 1)], "abyss": [(0x44, 1), (0x47, 1), (0x65, 1)],
    }

    def test_dungeon_area_mapping(self):
        from ultima_rov_dx import dx_patch
        t = dx_patch.build_tables(self.inputs["palettes"], self.inputs["bg_categories"], self.inputs["obj_categories"])
        names = list(t.theme_names)
        for theme, levels in self.DUNGEONS.items():
            for area, flag in levels:
                self.assertEqual(t.area_theme[256 * flag + area], names.index(theme), (theme, hex(area), flag))
        # surface atlas areas stay on theme 0 in their own half
        for area in (0x00, 0x02, 0x03, 0x04, 0x05, 0x32, 0x33, 0x4E, 0x51):
            self.assertEqual(t.area_theme[area], 0, hex(area))
        for area in (0x45, 0x46):
            self.assertEqual(t.area_theme[256 + area], 0, hex(area))
        # the same id differs between the halves: 00 castle / Injustice, 18 Hatred / Dishonor
        self.assertNotEqual(t.area_theme[0x18], t.area_theme[0x118])
        self.assertEqual(t.area_theme[0x100], names.index("injustice"))
        # every dungeon has its own theme and its own colours
        self.assertEqual(len({names.index(n) for n in self.DUNGEONS}), 8)
        bgs = {t.theme_bg_rom[64 * names.index(n):64 * names.index(n) + 64] for n in self.DUNGEONS}
        self.assertEqual(len(bgs), 8)
        for n in self.DUNGEONS:
            i = names.index(n)
            self.assertEqual(t.rt_slot[i], dx_patch.SLOT_MAP)
            pal = t.theme_bg_rom[64 * i:64 * i + 64]
            self.assertEqual(len({pal[p * 8:p * 8 + 2] for p in range(8)}), 1, n)   # shared floor colour 0
        self.assertEqual(t.rt_slot[0], dx_patch.SLOT_SURFACE)
        self.assertEqual(t.rt_slot[t.first_map], dx_patch.SLOT_MAP)
        # the Hatred look is the one cached in the dungeon slot at boot
        self.assertEqual(t.bg_themes[64 * dx_patch.SLOT_MAP:64 * dx_patch.SLOT_MAP + 64],
                         t.theme_bg_rom[64 * names.index("cavern"):64 * names.index("cavern") + 64])

    def test_surface_area_in_theme_rejected(self):
        from ultima_rov_dx import dx_patch
        bg = dict(self.inputs["bg_categories"])
        bg["area_themes"] = dict(bg["area_themes"], extra={"areas_alt": [0x46]})
        with self.assertRaises(dx_patch.PatchError):
            dx_patch.build_tables(self.inputs["palettes"], bg, self.inputs["obj_categories"])

    def test_obj_color0_is_white(self):
        from ultima_rov_dx import dx_patch
        t = dx_patch.build_tables(self.inputs["palettes"], self.inputs["bg_categories"], self.inputs["obj_categories"])
        # OBP0 $34 in the entrance cutscene shows shade 0 on the hero: white, as on DMG
        self.assertTrue(all(t.base_obj[p * 8:p * 8 + 2] == b"\xff\x7f" for p in range(8)))

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
            if (bank, addr) in GL.MAP_LCD_ON_SITES:
                mode = 0x00                      # nop: map screen
            elif (bank, addr) in GL.CARD_LCD_ON_SITES:
                mode = 0x49                      # ld c,c: dungeon title card
            elif (bank, addr) in GL.PICTURE_LCD_ON_SITES:
                mode = 0x52                      # ld d,d: entrance cutscene
            elif (bank, addr) in GL.BLANK_LCD_ON_SITES:
                mode = 0x5B                      # ld e,e: blank screen
            elif (bank, addr) in GL.MENU_LCD_ON_SITES:
                mode = 0x64                      # ld h,h: start menu
            elif (bank, addr) in GL.DIALOG_LCD_ON_SITES:
                mode = 0x6D                      # ld l,l: dialog text screen
            elif (bank, addr) in GL.CHAMPION_LCD_ON_SITES:
                mode = 0x7F                      # ld a,a: champion select
            else:
                mode = 0x40                      # ld b,b: text screen
            self.assertEqual(self.out[off + 1], mode)
        for bank, addr in GL.TITLE_LCD_ON_SITES:
            self.assertEqual(self.out[GL.file_offset(bank, addr)], 0xF7)

    def test_branding_on_logo(self):
        # palettes/branding.yaml: credit tiles in bank 8, cells for row 17 of the logo map
        from ultima_rov_dx import branding, dx_patch
        from ultima_rov_dx.sm83asm import assemble
        import yaml
        _, syms = assemble([("dx.asm", dx_patch._asm_source())])
        spec = yaml.safe_load((ROOT / "palettes" / "branding.yaml").read_text())
        tiles, cells = branding.build(spec)
        self.assertGreater(len(tiles), 0)
        tbl = GL.file_offset(GL.DX_RUNTIME_BANK, syms["BRAND_TILES"])
        self.assertEqual(self.out[tbl:tbl + len(tiles)], tiles)
        cel = GL.file_offset(GL.DX_RUNTIME_BANK, syms["BRAND_CELLS"])
        self.assertEqual(self.out[cel + 3 * len(cells) + 1], 0)          # terminator (hi = 0)
        rows = {r for r, _c, _t, _p in cells}
        self.assertEqual(rows, {spec["credit"]["row"], spec["plate"]["row"], spec["plate"]["row"] + 1})

    def test_theme_tables_in_rom(self):
        # bank 8 ROM theme tables: 512-byte area map (flag 0, flag 1), page aligned,
        # and the per-theme colours / WRAM slots the MapTheme routine reads
        import build_dx
        from ultima_rov_dx import dx_patch
        from ultima_rov_dx.sm83asm import assemble
        inputs = build_dx.load_inputs()
        t = dx_patch.build_tables(inputs["palettes"], inputs["bg_categories"], inputs["obj_categories"])
        _, syms = assemble([("dx.asm", dx_patch._asm_source())])
        self.assertEqual(syms["AREA_THEME"] & 0xFF, 0)
        self.assertEqual(syms["METAPAL"] & 0x7F, 0)
        for name, data in (("AREA_THEME", t.area_theme), ("METAPAL", t.metapal), ("THEME_BG_ROM", t.theme_bg_rom),
                           ("THEME_OBJ_ROM", t.theme_obj_rom), ("RT_SLOT", t.rt_slot)):
            off = GL.file_offset(GL.DX_RUNTIME_BANK, syms[name])
            self.assertEqual(self.out[off:off + len(data)], data, name)
            self.assertLessEqual(syms[name] + len(data), 0x8000, name)

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
