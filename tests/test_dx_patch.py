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
                         (256, 256, 256, 128 * dx_patch.MP_SETS))
        self.assertEqual((len(t.area_theme), len(t.bg_themes)), (512, 64 * dx_patch.MAX_THEMES))
        self.assertEqual((len(t.theme_bg_rom), len(t.rt_slot)), (64 * dx_patch.ROM_THEMES, dx_patch.ROM_THEMES))
        self.assertEqual(len(t.mp_idx), dx_patch.ROM_THEMES)
        self.assertTrue(all(v < dx_patch.MP_SETS for v in t.mp_idx))
        self.assertTrue(all(v < 8 for v in t.metapal + t.objpal + t.lut_title + t.lut_logo))
        # LUT_GAME: palette 0-7, plus attribute bit 3 (VRAM bank 1) on the gold panel digits only
        self.assertTrue(all(v & ~0x0F == 0 and (v & 8 == 0 or i in GL.DIGIT_TILES) for i, v in enumerate(t.lut_game)))
        self.assertTrue(all(v < themes for v in t.area_theme))
        self.assertEqual(t.bg_themes[:64], t.base_bg)

    def test_black_knight_not_royal(self):
        # issue #10: the Black Knight ($52) has its own natural colour, not Lord British's royal red
        from ultima_rov_dx import dx_patch
        t = dx_patch.build_tables(self.inputs["palettes"], self.inputs["bg_categories"], self.inputs["obj_categories"])
        names = list(self.inputs["palettes"]["obj_palettes"])
        self.assertEqual(names[t.objpal[0x4C]], "royal")              # Lord British
        self.assertIn(0x52, self.inputs["palettes"]["creatures"]["black_knight"]["ids"])
        self.assertNotIn(0x52, self.inputs["obj_categories"]["ids"]["royal"])

    def test_old_palette_knobs_rejected(self):
        # per-area OBJ tints, the fixed tier palettes and the knight borrow are gone
        import copy
        from ultima_rov_dx import dx_patch
        pal, obj, bg = self.inputs["palettes"], self.inputs["obj_categories"], self.inputs["bg_categories"]
        for key, val in (("tier_palettes", ["creature_a", "creature_b", "creature_c"]), ("knight_borrow", {"id": 0x52})):
            bad = copy.deepcopy(obj)
            bad[key] = val
            with self.assertRaises(dx_patch.PatchError):
                dx_patch.build_tables(pal, bg, bad)
        bad = copy.deepcopy(pal)
        bad["obj_themes"] = {"cavern": {}}
        with self.assertRaises(dx_patch.PatchError):
            dx_patch.build_tables(bad, bg, obj)

    def test_cavern_theme(self):
        from ultima_rov_dx import dx_patch
        t = dx_patch.build_tables(self.inputs["palettes"], self.inputs["bg_categories"], self.inputs["obj_categories"])
        ow = t.theme_names.index("overworld")
        self.assertEqual((t.area_theme[0x18], t.area_theme[0x19], t.area_theme[0x02], t.area_theme[0x00]), (1, 1, ow, ow))
        cav = t.bg_themes[64:128]
        # all 8 palettes (side panel included) share the cave floor as colour 0
        self.assertEqual({cav[p * 8:p * 8 + 2] for p in range(8)}, {cav[8:10]})
        self.assertNotEqual(cav[8:10], t.base_bg[8:10])

    def test_panel_icons_on_panel_colour(self):
        # every map theme: the palettes an A/B icon can use share the side panel's colour 0
        # (no tinted square); surface themes keep grass/water fields, IconPal falls back there
        from ultima_rov_dx import dx_patch
        t = dx_patch.build_tables(self.inputs["palettes"], self.inputs["bg_categories"], self.inputs["obj_categories"])
        bg = self.inputs["bg_categories"]
        pal = list(self.inputs["palettes"]["bg_palettes"])
        icon_pals = {pal.index(p) for p, ids in bg["item_palettes"].items() if ids}
        for name, spec in bg["area_themes"].items():
            if not (spec.get("areas") or spec.get("areas_alt")):
                continue
            k = t.theme_names.index(name)
            rom = t.theme_bg_rom[64 * k:64 * k + 64]
            skip = {pal.index("grass"), pal.index("water")} if spec.get("surface") else set()
            for p in icon_pals - skip:
                self.assertEqual(rom[8 * p:8 * p + 2], rom[0:2], f"{name}: {pal[p]}")
        # `earth` is the start-menu portrait palette: no item uses it
        self.assertFalse(bg["item_palettes"].get("earth"))
        self.assertNotIn(pal.index("earth"), set(t.item_pal))

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
        # the overworld, Lord British's throne room and the Abyss isle: `overworld` (theme 0 stays
        # for the title screens)
        for area in (0x00, 0x02, 0x03, 0x04, 0x05):
            self.assertEqual(t.area_theme[area], names.index("overworld"), hex(area))
        self.assertEqual(t.area_theme[256 + 0x46], names.index("overworld"))
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

    # places outside the dungeons: (area, flag) -> theme (reverse_engineering/notes/areas.md)
    PLACES = {
        "castle": [(0x30, 0), (0x31, 0)], "simon": [(0x32, 0), (0x33, 0)], "lycaeum_grounds": [(0x51, 0)],
        "lycaeum": [(0x52, 0), (0x53, 0), (0x54, 0)], "town": [(0x1D, 0), (0x4F, 0), (0x20, 0)],
        "market": [(0x4E, 0), (0x45, 1)], "catslair": [(0x1E, 0), (0x50, 0)], "sidecave": [(0x29, 0), (0x21, 0)],
        "abbey": [(0x55, 0), (0x01, 0)], "gypsy": [(0x1F, 0)],
    }

    def test_place_area_mapping(self):
        from ultima_rov_dx import dx_patch
        t = dx_patch.build_tables(self.inputs["palettes"], self.inputs["bg_categories"], self.inputs["obj_categories"])
        names = list(t.theme_names)
        for theme, areas in self.PLACES.items():
            for area, flag in areas:
                self.assertEqual(t.area_theme[256 * flag + area], names.index(theme), (theme, hex(area), flag))
        self.assertGreater(len(names), 16)               # the table outgrew the old 16-theme cap
        self.assertEqual(t.area_theme[0x22], names.index("cavern"))        # unreached copy of Hatred 23
        self.assertEqual(t.area_theme[0x108], names.index("injustice"))
        # every valid area id ($D13E = 0: $00-$55, $D13E = 1: $00-$65) has an explicit theme or is surface
        bg = self.inputs["bg_categories"]
        listed = {(a, 0) for a in bg["surface_areas"]} | {(a, 1) for a in bg["surface_areas_alt"]}
        for spec in bg["area_themes"].values():
            listed |= {(a, 0) for a in spec.get("areas") or []} | {(a, 1) for a in spec.get("areas_alt") or []}
        missing = [(hex(a), f) for f, top in ((0, 0x55), (1, 0x65)) for a in range(top + 1) if (a, f) not in listed]
        self.assertEqual(missing, [])
        # gold colours the side-panel stars and coin: it stays gold in every theme
        gold = list(self.inputs["palettes"]["bg_palettes"]).index("gold")
        scene_themes = {spec.get("theme") for spec in (bg.get("scenes") or {}).values()}
        for i, n in enumerate(names):
            if n in ("entrance", "menu") or n in scene_themes:        # no side panel on these screens
                continue
            r, g, b = (lambda v: (v & 31, (v >> 5) & 31, v >> 10))(int.from_bytes(t.theme_bg_rom[64 * i + 8 * gold + 2:64 * i + 8 * gold + 4], "little"))
            self.assertTrue(r > 20 and g > 15 and b < 14, (n, r, g, b))
        # themes share metatile palette maps: fewer sets than themes
        self.assertLess(len(set(t.mp_idx[:len(names)])), len(names))
        self.assertEqual(t.mp_idx[0], 0)

    def test_surface_theme_needs_flag(self):
        from ultima_rov_dx import dx_patch
        bg = dict(self.inputs["bg_categories"])
        themes = dict(bg["area_themes"])
        themes["simon"] = {k: v for k, v in themes["simon"].items() if k != "surface"}
        bg["area_themes"] = themes
        with self.assertRaises(dx_patch.PatchError):
            dx_patch.build_tables(self.inputs["palettes"], bg, self.inputs["obj_categories"])
        themes["simon"] = dict(themes["simon"], surface=True, areas=[0x30])   # 0x30 is not a surface area
        themes["castle"] = {"areas": [0x31]}
        with self.assertRaises(dx_patch.PatchError):
            dx_patch.build_tables(self.inputs["palettes"], bg, self.inputs["obj_categories"])

    def test_surface_area_in_theme_rejected(self):
        from ultima_rov_dx import dx_patch
        bg = dict(self.inputs["bg_categories"])
        bg["area_themes"] = dict(bg["area_themes"], extra={"areas_alt": [0x46]})
        with self.assertRaises(dx_patch.PatchError):
            dx_patch.build_tables(self.inputs["palettes"], bg, self.inputs["obj_categories"])

    def _tables(self, pal=None, bg=None):
        from ultima_rov_dx import dx_patch
        return dx_patch.build_tables(pal or self.inputs["palettes"], bg or self.inputs["bg_categories"],
                                     self.inputs["obj_categories"])

    def _scenes(self, t):
        ent = []
        for i in range(0, len(t.scenes) - 2, 5):
            lo, hi, theme, lut, obj = t.scenes[i:i + 5]
            ent.append((lo | hi << 8, theme, lut, obj))
        self.assertEqual(t.scenes[-2:], b"\0\0")
        return ent

    def test_scene_tables(self):
        # ending, credits, death screen, rune shrine...: one SCENES entry per LCD-on site
        from ultima_rov_dx import dx_patch
        t = self._tables()
        ent = self._scenes(t)
        self.assertEqual(len(ent), len(t.scene_names))
        scenes = self.inputs["bg_categories"]["scenes"]
        self.assertTrue({"rune_shrine", "ending_text", "ending_throne", "death", "credits", "high_scores",
                         "parade", "title_card"} <= set(scenes))
        sites = [tuple(s) for spec in scenes.values() for s in spec["sites"]]
        self.assertEqual(len(sites), len(ent))
        self.assertEqual(len(set(a for _b, a in sites)), len(sites), "return addresses must be unique")
        for (bank, addr), (ret, theme, lut, obj), name in zip(sites, ent, t.scene_names):
            self.assertIn((bank, addr), GL.GAME_LCD_ON_SITES)
            self.assertNotIn((bank, addr), GL.MAP_LCD_ON_SITES)
            self.assertEqual(ret, addr + 1, name)          # rst $28 at the site returns to the mode byte
            if name == "title_card":
                self.assertEqual((theme, lut, obj), (0xFF, 0xFF, 0xFF))
                continue
            self.assertEqual(t.theme_names[theme], scenes[name]["theme"])
            self.assertNotIn(theme, t.area_theme, "scene themes are not map themes")
            self.assertTrue(lut == 0xFF or lut < len(t.scene_luts) // 256)
            self.assertTrue(obj == 0xFF or obj < len(t.scene_obj) // 8)
        self.assertLessEqual(len(t.scene_luts) // 256, dx_patch.MAX_SCENE_LUTS)
        self.assertEqual(len(t.scene_luts) % 256, 0)
        named = dict(zip(t.scene_names, ent))
        self.assertNotEqual(named["ending_throne"][2], 0xFF)           # throne room: own picture LUT
        self.assertNotEqual(named["death"][3], 0xFF)                   # death screen: star sprites
        # the text screens after a rune and the 2-player wait screen are dialogs (text + side panel)
        self.assertLessEqual({(0, 0x0AEB), (0, 0x14FF)}, GL.DIALOG_LCD_ON_SITES)

    def test_scene_errors(self):
        from ultima_rov_dx import dx_patch
        bg0 = self.inputs["bg_categories"]
        def bad(scenes=None, pal=None):
            bg = dict(bg0)
            if scenes is not None:
                bg["scenes"] = scenes
            with self.assertRaises(dx_patch.PatchError):
                self._tables(pal=pal, bg=bg)
        sc = bg0["scenes"]
        bad(dict(sc, x={"sites": [[7, 0x4A40]], "theme": "nope"}))                      # unknown theme
        bad(dict(sc, x={"sites": [[0, 0x23E2]], "theme": "royal"}))                     # map site
        bad(dict(sc, x={"sites": [[7, 0x4A40]], "theme": "royal"}))                     # duplicate site
        bad(dict(sc, x={"sites": [[7, 0x4AE3]], "theme": "cavern"}))                    # area theme
        bad(dict(sc, title_card={"sites": [[7, 0x4619]], "tint": True, "theme": "royal"}))
        bad(dict(sc, title_card={"sites": [[7, 0x4A40]], "tint": True}))                # not a card site
        pal = dict(self.inputs["palettes"])
        pal["scene_obj"] = dict(pal["scene_obj"], unused={"colors": ["#FFFFFF", "#C0C0C0", "#808080", "#000000"]})
        bad(pal=pal)                                                                    # unused scene_obj
        pal = dict(self.inputs["palettes"], card_tints={16: {"colors": ["#000000"] * 4}})
        bad(pal=pal)                                                                    # card number > 15

    def test_card_tints(self):
        # card number (HRAM $FF8F) -> UI palette; numbers without a tint keep the entrance card
        t = self._tables()
        self.assertEqual(len(t.card_tint), 128)
        names = self.inputs["palettes"]["bg_themes"]
        ent = t.theme_names.index(self.inputs["bg_categories"]["entrance_theme"])
        entrance_ui = t.theme_bg_rom[64 * ent + 8 * t.card_ui:64 * ent + 8 * t.card_ui + 8]
        cards = [t.card_tint[8 * i:8 * i + 8] for i in range(16)]
        self.assertEqual(cards[1], entrance_ui)                       # the Cavern of Hatred: unchanged
        tinted = sorted(self.inputs["palettes"]["card_tints"])
        self.assertEqual(tinted, [2, 3, 4, 5, 6, 7, 9])
        self.assertEqual(len({cards[i] for i in tinted} | {entrance_ui}), len(tinted) + 1)
        self.assertIn("entrance", names)

    def test_gold_digits(self):
        # side-panel digits: map LUT selects VRAM bank 1 on the gold palette; the
        # redrawn glyphs are colour 1 with a colour-3 shadow (never colour 2)
        from ultima_rov_dx import dx_patch
        t = self._tables()
        gold = dx_patch.P.names(self.inputs["palettes"], "bg_palettes").index("gold")
        self.assertEqual(t.digit_pal, gold)
        self.assertTrue(all(t.lut_game[i] == gold | 8 for i in GL.DIGIT_TILES))
        if not ROM.is_file():
            self.skipTest("original ROM not present")
        orig = ROM.read_bytes()
        g = dx_patch.gold_digits(orig)
        self.assertEqual(len(g), 16 * len(GL.DIGIT_TILES))
        font = orig[GL.file_offset(*GL.DIGIT_FONT):][:len(g)]
        for i in range(0, len(g), 2):
            lo, hi = g[i], g[i + 1]
            self.assertEqual(hi & ~lo, 0)                             # no colour 2
            self.assertEqual(lo & ~hi, font[i])                       # colour 1 = the original glyph
        off = GL.file_offset(*GL.DIGIT_FONT)
        with self.assertRaises(dx_patch.PatchError):              # not a solid colour-3 glyph: refuse
            dx_patch.gold_digits(orig[:off] + b"\xff\x00" + orig[off + 2:])

    def test_hero_palettes(self):
        # one OBJ palette 0 per champion ($D133 order) + portrait colours for BG palettes 1-4
        from ultima_rov_dx import dx_patch
        t = dx_patch.build_tables(self.inputs["palettes"], self.inputs["bg_categories"], self.inputs["obj_categories"])
        names = [h["name"] for h in self.inputs["palettes"]["heroes"]]
        self.assertEqual(names, ["Mariah", "Iolo", "Dupre", "Shamino"])
        self.assertEqual((len(t.hero_obj), len(t.hero_bg)), (32, 32))
        objs = [t.hero_obj[8 * i:8 * i + 8] for i in range(4)]
        self.assertEqual(len(set(objs)), 4, "each champion needs distinct sprite colours")
        self.assertEqual(len({t.hero_bg[8 * i:8 * i + 8] for i in range(4)}), 4)
        self.assertTrue(all(o[:2] == t.base_obj[:2] == b"\xff\x7f" for o in objs))

    def test_champion_portraits_use_hero_palettes(self):
        # portrait tiles on the select screen: Mariah $10-$1F, Iolo $20-$2F, Dupre $30-$3F, Shamino $80-$8F
        from ultima_rov_dx import dx_patch
        t = dx_patch.build_tables(self.inputs["palettes"], self.inputs["bg_categories"], self.inputs["obj_categories"])
        tr = t.text_ranges
        n_text = tr[0]
        champ = tr[1 + 3 * n_text:]
        rngs = {(champ[1 + 3 * i], champ[2 + 3 * i]): champ[3 + 3 * i] for i in range(champ[0])}
        for hero, (first, last) in enumerate(((0x10, 0x1F), (0x20, 0x2F), (0x30, 0x3F), (0x80, 0x8F))):
            self.assertEqual(rngs.get((first, last)), 1 + hero, f"champion {hero} portrait")

    def test_heroes_need_four(self):
        from ultima_rov_dx import dx_patch
        pal = dict(self.inputs["palettes"])
        pal["heroes"] = pal["heroes"][:3]
        with self.assertRaises(dx_patch.PatchError):
            dx_patch.build_tables(pal, self.inputs["bg_categories"], self.inputs["obj_categories"])
        bad = [dict(h) for h in self.inputs["palettes"]["heroes"]]
        bad[0]["sprite"] = ["#000000"] + bad[0]["sprite"][1:]
        pal["heroes"] = bad
        with self.assertRaises(dx_patch.PatchError):
            dx_patch.build_tables(pal, self.inputs["bg_categories"], self.inputs["obj_categories"])

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

    def test_live_interrupt_vectors_kept(self):
        # PrepTramp sits in vector padding: the jumps/retis the game takes stay
        self.assertEqual(self.out[0x40:0x43], self.original[0x40:0x43])   # VBlank: jp $1ACB
        self.assertEqual(self.out[0x48:0x4B], self.original[0x48:0x4B])   # STAT: jp $1A9F
        self.assertEqual(self.out[0x50], 0xD9)                            # timer: reti
        self.assertEqual(self.out[0x58:0x5B], self.original[0x58:0x5B])   # serial: jp $C550
        self.assertEqual(self.out[0x60], 0xD9)                            # joypad: reti
        from ultima_rov_dx import dx_patch
        from ultima_rov_dx.sm83asm import assemble
        _, syms = assemble([("dx.asm", dx_patch._asm_source())])
        tramp = syms["PrepTramp"]
        self.assertEqual(self.out[0x02EA:0x02EE], bytes([0xCD, tramp & 0xFF, tramp >> 8, 0xC8]))  # VBlank-flag wait
        self.assertEqual(self.out[0x02DC:0x02E0], self.original[0x02DC:0x02E0])  # LY-145 wait: timing-exact, not hooked
        wait = syms["PrepWait"]
        self.assertEqual(self.out[0x175A:0x175D], bytes([0xCD, wait & 0xFF, wait >> 8]))  # animated-tile copy
        self.assertEqual(self.out[0x1EE7:0x1EEB], bytes([0xCD, tramp & 0xFF, tramp >> 8, 0x76]))  # main loop: then halt

    def test_only_expected_bytes_change(self):
        allowed = set(range(0x0003, 0x0038)) | set(range(0x0061, 0x0100)) | {0x143, 0x148, 0x14D, 0x14E, 0x14F}
        allowed |= set(range(0x0043, 0x0048)) | set(range(0x004B, 0x0050)) | set(range(0x0051, 0x0058)) | set(range(0x005B, 0x0060))  # vector padding
        for h in GL.HOOKS:
            allowed |= set(range(h.offset, h.offset + len(h.preimage)))
        allowed |= set(range(*GL.BANK2_FREE))           # AllocHook + TIER_TAB (was $FF fill)
        allowed |= set(range(*GL.BANK7_FREE))           # ParadeLoad (was $FF fill)
        for bank, addr in GL.GAME_LCD_ON_SITES + GL.TITLE_LCD_ON_SITES:
            off = GL.file_offset(bank, addr)
            allowed |= {off, off + 1}
        changed = {i for i in range(len(self.original)) if self.original[i] != self.out[i]}
        self.assertEqual(changed - allowed, set())
        self.assertEqual(self.out[len(self.original):len(self.original) + 3][:1], b"\xf0")  # bank 8 starts with code

    def test_parade_sprites(self):
        # attract-loop parade: both loader calls go through ParadeLoad, which notes the
        # list and jumps on to the original loader; every graphic gets its natural colour
        # in a palette planned per page (creatures.parade_plan)
        from ultima_rov_dx import dx_patch
        from ultima_rov_dx.sm83asm import assemble
        _, syms = assemble([("dx.asm", dx_patch._asm_source())])
        load = syms["ParadeLoad"]
        call = bytes([0xCD, load & 0xFF, load >> 8])
        self.assertEqual(self.out[GL.file_offset(7, 0x47F4):GL.file_offset(7, 0x47FA)], bytes.fromhex("11a67c") + call)
        self.assertEqual(self.out[GL.file_offset(7, 0x48D3):GL.file_offset(7, 0x48D7)], bytes.fromhex("d1") + call)
        off = GL.file_offset(7, load)
        self.assertEqual(self.out[off:off + 6], bytes([0x7B, 0xE0, syms["PARADE_LIST"] & 0xFF, 0xC3, 0xEE, 0x49]))
        import build_dx
        inp = build_dx.load_inputs()
        cr = dx_patch.creatures(self.original, inp["palettes"], inp["obj_categories"])
        plan = dx_patch.parade_plan(self.original, cr)
        tab = self.out[GL.file_offset(8, syms["PARADE_PAL_ROM"]):][:syms["PARADE_LEN"]]
        self.assertEqual(tab, plan.pal)
        for k, page in enumerate(plan.pages):
            for name, p in page.items():
                c = cr.cls(name)
                self.assertEqual(plan.colors[64 * k + 8 * p:64 * k + 8 * p + 8], cr.class_col[8 * c:8 * c + 8], name)
        self.assertEqual(plan.pages[0], {"royal": 1, "folk": 2})      # Lord British: royal, as in his castle
        self.assertEqual(plan.pages[2], {"troll": 3, "ghost": 4, "gremlin": 5, "slime": 6})
        b9 = GL.file_offset(9, 0x4000) - 0x4000
        self.assertEqual(self.out[b9 + syms["NAT_PARADE"]:][:len(plan.colors)], plan.colors)
        self.assertEqual(self.out[b9 + syms["NAT_PLIST"]:][:len(plan.plist)], plan.plist)

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
        for name, n in (("RT_SLOT", dx_patch.ROM_THEMES), ("MP_IDX", dx_patch.ROM_THEMES)):
            self.assertLessEqual((syms[name] & 0xFF) + n, 0x100, name)   # indexed by low byte only
        for name, data in (("AREA_THEME", t.area_theme), ("METAPAL", t.metapal), ("THEME_BG_ROM", t.theme_bg_rom),
                           ("RT_SLOT", t.rt_slot), ("MP_IDX", t.mp_idx)):
            off = GL.file_offset(GL.DX_RUNTIME_BANK, syms[name])
            self.assertEqual(self.out[off:off + len(data)], data, name)
            self.assertLessEqual(syms[name] + len(data), 0x8000, name)

    def test_hero_tables_in_rom(self):
        import build_dx
        from ultima_rov_dx import dx_patch
        from ultima_rov_dx.sm83asm import assemble
        t = dx_patch.build_tables(*(build_dx.load_inputs()[k] for k in ("palettes", "bg_categories", "obj_categories")))
        _, syms = assemble([("dx.asm", dx_patch._asm_source())])
        self.assertEqual((syms["HERO_ID"], syms["HERO_BG"]), (0xD133, syms["LUT_GAME"]))
        off = GL.file_offset(GL.DX_RUNTIME_BANK, syms["HERO_OBJ_ROM"])
        self.assertEqual(self.out[off:off + 32], t.hero_obj)
        w2 = GL.file_offset(GL.DX_RUNTIME_BANK, syms["W2_IMAGE_ROM"]) - syms["W2_BASE"]
        self.assertEqual(self.out[w2 + syms["HERO_BG"]:w2 + syms["HERO_BG"] + 32], t.hero_bg)
        self.assertEqual(self.out[w2 + syms["HERO_CACHED"]], 0xFF)            # first Slot always loads

    def test_champion_sprite_colours(self):
        # start a game as each champion: OBJ palette 0 (the player) follows $D133, palettes 1-7 don't
        try:
            from pyboy import PyBoy
        except ImportError:
            self.skipTest("pyboy not installed (uv sync --extra emu)")
        import tempfile
        import build_dx
        import capture_screens as cs
        from ultima_rov_dx import dx_patch
        t = dx_patch.build_tables(*(build_dx.load_inputs()[k] for k in ("palettes", "bg_categories", "obj_categories")))

        def objpal(pb):
            out = bytearray()
            for i in range(64):
                pb.memory[0xFF6A] = i
                out.append(pb.memory[0xFF6B])
            return bytes(out)

        pals = []
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as d:
            rom = Path(d) / "dx.gbc"
            rom.write_bytes(self.out)
            for hero in range(4):
                pb = PyBoy(str(rom), window="null", cgb=True, sound_emulated=False)
                pb.set_emulation_speed(0)
                hit = []
                pb.hook_register(3, cs.CHARACTER_SELECT_LCD_ON, lambda _c: hit.append(1), None)
                for _scene, actions in cs.ROUTE[:3]:
                    for button, hold, after in actions:
                        if button:
                            pb.button_press(button); pb.tick(hold, True); pb.button_release(button)
                        pb.tick(max(after, 1), True)
                for _ in range(60):
                    pb.button_press("start"); pb.tick(6, True); pb.button_release("start")
                    for _ in range(54):
                        pb.tick(1, True)
                        if hit:
                            break
                    if hit:
                        break
                pb.tick(54, True)
                # select cursor = $D133; it starts on Shamino and each Right/A step moves it
                for b, n, after in (("right", (hero - 1) % 4, 40), ("a", 6, 54), ("start", 3, 54), ("a", 15, 90)):
                    for _ in range(n):
                        pb.button_press(b); pb.tick(6, True); pb.button_release(b); pb.tick(after, True)
                self.assertEqual(pb.memory[1, 0xD133], hero)    # WRAM1 (SVBK may be 2 in VBlank)
                pals.append(objpal(pb))
                pb.stop(save=False)
        for hero, p in enumerate(pals):
            self.assertEqual(p[:8], t.hero_obj[8 * hero:8 * hero + 8], f"champion {hero}")
        self.assertEqual(len({p[8:] for p in pals}), 1, "monster/NPC palettes must not depend on the champion")

    def test_scene_tables_in_rom(self):
        import build_dx
        from ultima_rov_dx import dx_patch
        from ultima_rov_dx.sm83asm import assemble
        t = dx_patch.build_tables(*(build_dx.load_inputs()[k] for k in ("palettes", "bg_categories", "obj_categories")))
        _, syms = assemble([("dx.asm", dx_patch._asm_source())])
        def at(name, n):
            off = GL.file_offset(GL.DX_RUNTIME_BANK, syms[name])
            return self.out[off:off + n]
        self.assertEqual(at("SCENES", len(t.scenes)), t.scenes)
        self.assertEqual(at("SCENE_LUTS", len(t.scene_luts)), t.scene_luts)
        self.assertEqual(at("SCENE_OBJ", len(t.scene_obj)), t.scene_obj)
        sig = at("BANK_SIG", 7)
        self.assertEqual(sig, bytes(self.original[b * 0x4000 + 1] for b in range(1, 8)))
        self.assertEqual(len(set(sig)), 7)
        self.assertEqual(at("CARD_TINT", 128), t.card_tint)
        self.assertEqual(at("CARD_UI", 1)[0], (syms["BASE_BG"] + 8 * t.card_ui) & 0xFF)
        self.assertEqual(at("GOLD_DIGITS", 160), dx_patch.gold_digits(self.original))
        self.assertEqual(syms["DIGIT_VRAM"], 0x8E80)                  # tile $E8, signed tile data
        self.assertEqual(syms["HR_CARD"], 0xFF8F)
        # the card routine stores the card number in $FF8F before its LCD-on
        self.assertEqual(self.original[GL.file_offset(7, 0x4608):][:2], b"\xe0\x8f")

    def test_ending_scenes_colour(self):
        # all eight runes ($D135 = $FF) on the overworld: the ending text, the throne room and
        # the credits each get their scene theme, and the game carries on into the attract loop
        try:
            from pyboy import PyBoy
        except ImportError:
            self.skipTest("pyboy not installed (uv sync --extra emu)")
        import tempfile
        import build_dx
        import capture_screens as cs
        from ultima_rov_dx import dx_patch
        t = dx_patch.build_tables(*(build_dx.load_inputs()[k] for k in ("palettes", "bg_categories", "obj_categories")))

        def colours(pb):
            out = set()
            for i in range(0, 64, 2):
                pb.memory[0xFF68] = i
                lo = pb.memory[0xFF69]
                pb.memory[0xFF68] = i + 1
                out.add(lo | pb.memory[0xFF69] << 8)
            return out

        def theme_colours(name):
            k = t.theme_names.index(name)
            rom = t.theme_bg_rom[64 * k:64 * k + 64]
            return {rom[i] | rom[i + 1] << 8 for i in range(0, 64, 2)}

        seen = {}
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as d:
            rom = Path(d) / "dx.gbc"
            rom.write_bytes(self.out)
            pb = PyBoy(str(rom), window="null", cgb=True, sound_emulated=False)
            pb.set_emulation_speed(0)
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
            ev = []
            for site in ((7, 0x4A40), (7, 0x4AE3), (7, 0x4C32), (7, 0x4C78)):
                pb.hook_register(site[0], site[1], lambda _c, s=site: ev.append(s), None)
            pb.memory[1, 0xD135] = 0xFF
            for f in range(3000):
                pb.tick(1, True)
                if ev and ev[-1] not in seen:
                    pb.tick(30, True)
                    seen[ev[-1]] = colours(pb)
                if ev and ev[-1] in ((7, 0x4A40), (7, 0x4AE3)) and f % 60 == 59:   # the ending waits for a button;
                    pb.button_press("a"); pb.tick(6, True); pb.button_release("a")  # the attract loop runs alone
                if (7, 0x4C78) in seen:
                    break
            pb.stop(save=False)
        self.assertEqual(set(seen), {(7, 0x4A40), (7, 0x4AE3), (7, 0x4C32), (7, 0x4C78)})
        for site, theme in (((7, 0x4A40), "royal"), ((7, 0x4AE3), "throne"), ((7, 0x4C32), "credits"),
                            ((7, 0x4C78), "credits")):
            self.assertLessEqual(seen[site], theme_colours(theme), f"{site}: {theme}")
            self.assertGreaterEqual(len(seen[site]), 2)

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
