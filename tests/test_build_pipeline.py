import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import yaml  # noqa: F401
except ImportError:  # pragma: no cover
    yaml = None

from ultima_rov_dx import asm, rom_utils  # noqa: E402
from _synthetic import synthetic_rom  # noqa: E402


@unittest.skipIf(yaml is None, "pyyaml not installed; run via `uv run`")
class PalettePipelineTest(unittest.TestCase):
    def test_project_palettes_encode(self):
        from ultima_rov_dx import palettes
        encoded = palettes.encode(palettes.load(ROOT / "palettes/rov_palettes.yaml"))
        self.assertEqual(len(encoded["bg"]), 64)
        self.assertEqual(len(encoded["obj"]), 64)

    def test_bad_color_rejected(self):
        from ultima_rov_dx import palettes
        with self.assertRaises(ValueError):
            palettes.bgr555("8000")
        with self.assertRaises(ValueError):
            palettes.bgr555("FFF")


@unittest.skipIf(yaml is None, "pyyaml not installed; run via `uv run`")
class BuilderTest(unittest.TestCase):
    def setUp(self):
        import build_dx
        from ultima_rov_dx import palettes
        self.build_dx = build_dx
        self.encoded = palettes.encode(palettes.load(ROOT / "palettes/rov_palettes.yaml"))

    def test_full_build_refuses_until_reverse_engineering_is_done(self):
        with self.assertRaises(self.build_dx.IncompleteReverseEngineering):
            self.build_dx.build(synthetic_rom(), self.encoded)

    def test_header_only_build(self):
        original = synthetic_rom()
        out = self.build_dx.build(original, self.encoded, header_only=True)
        hdr = rom_utils.parse_header(out)
        self.assertEqual(len(out), len(original))
        self.assertEqual(hdr["cgb_flag"], 0x80)
        self.assertEqual(hdr["header_checksum"], hdr["header_checksum_calc"])
        self.assertEqual(hdr["global_checksum"], hdr["global_checksum_calc"])
        diff = [i for i in range(len(out)) if out[i] != original[i]]
        self.assertTrue(set(diff) <= {0x143, 0x14D, 0x14E, 0x14F})


class AsmTest(unittest.TestCase):
    def test_cram_loader_bytes(self):
        code = asm.cram_loader(0x7F00)
        self.assertEqual(code[:3], bytes([0x21, 0x00, 0x7F]))
        self.assertEqual(code[-1], 0xC9)
        self.assertEqual(code.count(bytes([0x20, 0xFA])), 2)  # two JR NZ,-6 loops

    def test_forward_jr(self):
        a = asm.Asm()
        a.jr(0x18, "end").db(0x00, 0x00).label("end").db(0xC9)
        self.assertEqual(a.finish(), bytes([0x18, 0x02, 0x00, 0x00, 0xC9]))


if __name__ == "__main__":
    unittest.main()
