import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ultima_rov_dx.sm83asm import AsmError, assemble  # noqa: E402


def asm(text: str, org: int = 0x100) -> bytes:
    secs, _ = assemble([("t", f"section s, 0, {org}\n{text}\n")])
    return bytes(secs[0].data)


class EncodingTest(unittest.TestCase):
    # expected bytes cross-checked against mgbdis output for the real ROM
    CASES = {
        "ld a, [$c522]": "fa22c5",
        "ldh [$ff8e], a": "e08e",
        "ldh a, [$44]": "f044",
        "ld [$c54e], sp": "084ec5",
        "ld hl, sp+9": "f809",
        "ld sp, hl": "f9",
        "ld [hl], $4b": "364b",
        "ld e, [hl]": "5e",
        "ld a, [hl+]": "2a",
        "ld [c], a": "e2",
        "ldh a, [c]": "f2",
        "add hl, de": "19",
        "adc $02": "ce02",
        "cp [hl]": "be",
        "sub a, 4": "d604",
        "push af": "f5",
        "pop hl": "e1",
        "res 0, c": "cb81",
        "bit 7, e": "cb7b",
        "srl e": "cb3b",
        "rst $28": "ef",
        "jp hl": "e9",
        "call nz, $1234": "c43412",
        "ret c": "d8",
        "stop": "1000",
    }

    def test_encodings(self):
        for text, hexbytes in self.CASES.items():
            with self.subTest(text=text):
                self.assertEqual(asm(text).hex(), hexbytes)

    def test_labels_and_jr(self):
        code = asm("start:\n  jr .fwd\n  nop\n.fwd:\n  jr start\n  jp start")
        self.assertEqual(code.hex(), "18010018fbc30001")

    def test_equ_and_expressions(self):
        code = asm("X equ $D600\n ld h, high(X)\n ld a, low(X+1)\n db 1, X >> 8\n dw X")
        self.assertEqual(code.hex(), "26d63e0101d600d6")

    def test_jr_out_of_range(self):
        with self.assertRaises(AsmError):
            asm("a:\n ds 200\n jr a")

    def test_undefined_symbol(self):
        with self.assertRaises(AsmError):
            asm("jp nowhere")


if __name__ == "__main__":
    unittest.main()
