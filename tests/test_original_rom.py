import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ultima_rov_dx import original_rom  # noqa: E402
from _synthetic import synthetic_rom  # noqa: E402


class OriginalRomTest(unittest.TestCase):
    def test_expected_location(self):
        self.assertEqual(original_rom.ORIGINAL_ROM_PATH,
                         ROOT / "rom" / "Ultima - Runes of Virtue (USA).gb")

    def test_known_dump_table_is_well_formed(self):
        self.assertEqual(sum(d.supported for d in original_rom.KNOWN_DUMPS), 1)
        for d in original_rom.KNOWN_DUMPS:
            self.assertEqual(len(d.md5), 32)
            self.assertEqual(len(d.sha1), 40)
            self.assertEqual(len(d.crc32), 8)

    def test_missing_rom_fails_clearly(self):
        with tempfile.TemporaryDirectory() as scratch:
            missing = Path(scratch) / "nope.gb"
            with self.assertRaises(original_rom.RomError) as ctx:
                original_rom.require_original_rom(missing)
            self.assertEqual(ctx.exception.status, original_rom.EXIT_ROM_MISSING)
            self.assertIn("original ROM not found", str(ctx.exception))
            self.assertIn(str(missing), str(ctx.exception))

    def test_wrong_rom_is_rejected(self):
        with tempfile.TemporaryDirectory() as scratch:
            fake = Path(scratch) / "fake.gb"
            fake.write_bytes(synthetic_rom())
            with self.assertRaises(original_rom.RomError) as ctx:
                original_rom.require_original_rom(fake)
            self.assertEqual(ctx.exception.status, original_rom.EXIT_ROM_MISMATCH)

    def test_check_rom_script_exit_code_without_rom(self):
        with tempfile.TemporaryDirectory() as scratch:
            env = dict(os.environ, ULTIMA_ROV_ROM=str(Path(scratch) / "absent.gb"))
            result = subprocess.run([sys.executable, str(ROOT / "scripts/check_rom.py")],
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 66)
            self.assertIn("original ROM not found", result.stderr)


if __name__ == "__main__":
    unittest.main()
