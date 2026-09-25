import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ultima_rov_dx import patch_builder, rom_utils  # noqa: E402
from _synthetic import synthetic_rom  # noqa: E402


class HeaderTest(unittest.TestCase):
    def test_parse_and_checksums(self):
        hdr = rom_utils.parse_header(synthetic_rom())
        self.assertEqual(hdr["title"], "SYNTHETIC TEST")
        self.assertEqual(hdr["cartridge_type_name"], "MBC1+RAM+BATTERY")
        self.assertEqual(hdr["rom_size_expected"], 0x20000)
        self.assertEqual(hdr["header_checksum"], hdr["header_checksum_calc"])
        self.assertEqual(hdr["global_checksum"], hdr["global_checksum_calc"])

    def test_cgb_flag_and_fixups(self):
        rom = rom_utils.set_cgb_supported(synthetic_rom())
        rom = rom_utils.fix_global_checksum(rom)
        hdr = rom_utils.parse_header(rom)
        self.assertEqual(hdr["cgb_flag"], 0x80)
        self.assertEqual(hdr["cgb_support"], "CGB-supported")
        self.assertEqual(hdr["header_checksum"], hdr["header_checksum_calc"])
        self.assertEqual(hdr["global_checksum"], hdr["global_checksum_calc"])


class IpsTest(unittest.TestCase):
    def test_round_trip_with_expansion(self):
        original = synthetic_rom()
        modified = bytearray(original)
        modified[0x143] = 0x80
        modified[0x1000:0x1010] = bytes(range(16))
        modified += bytes([0xAA]) * 0x4000  # grow by one bank
        patch = patch_builder.build_ips_patch(original, bytes(modified))
        self.assertTrue(patch.startswith(b"PATCH") and patch.endswith(b"EOF"))
        self.assertEqual(patch_builder.apply_ips_patch(original, patch), bytes(modified))


if __name__ == "__main__":
    unittest.main()
