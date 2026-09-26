"""Minimal two-pass SM83 (Game Boy CPU) assembler.

Pure Python so the patch builder has no external toolchain dependency.
Syntax is RGBDS-like (lower case mnemonics, ``[hl]``, ``ldh [$ff00+n], a``)
and deliberately small:

* ``label:`` defines a global label; ``.name:`` defines a local label that
  is scoped to the previous global label (referenced as ``.name``).
* ``section NAME, ROM_OFFSET, ORG`` starts a new output section: bytes are
  placed at file offset ``ROM_OFFSET`` and addresses count from ``ORG``.
  ``ROM_OFFSET`` may be ``none`` for sections that only define symbols.
* ``db``, ``dw``, ``ds COUNT[, FILL]``, ``equ`` via ``NAME equ EXPR``,
  ``align N`` (pads with $FF).
* Expressions are Python expressions over symbols, with ``$1F`` hex,
  ``%0101`` binary, ``low()``/``high()`` helpers.

Every instruction encodes to a fixed size independent of operand values,
so pass 1 can size everything with unresolved symbols treated as 0.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

R8 = {"b": 0, "c": 1, "d": 2, "e": 3, "h": 4, "l": 5, "[hl]": 6, "a": 7}
R16 = {"bc": 0, "de": 1, "hl": 2, "sp": 3}
R16_STK = {"bc": 0, "de": 1, "hl": 2, "af": 3}
COND = {"nz": 0, "z": 1, "nc": 2, "c": 3}
ALU = {"add": 0, "adc": 1, "sub": 2, "sbc": 3, "and": 4, "xor": 5, "or": 6, "cp": 7}
CBOPS = {"rlc": 0, "rrc": 1, "rl": 2, "rr": 3, "sla": 4, "sra": 5, "swap": 6, "srl": 7}
BITOPS = {"bit": 0x40, "res": 0x80, "set": 0xC0}
SIMPLE = {
    "nop": [0x00], "halt": [0x76], "stop": [0x10, 0x00], "di": [0xF3], "ei": [0xFB],
    "ret": [0xC9], "reti": [0xD9], "rlca": [0x07], "rrca": [0x0F], "rla": [0x17],
    "rra": [0x1F], "daa": [0x27], "cpl": [0x2F], "scf": [0x37], "ccf": [0x3F],
}


class AsmError(Exception):
    pass


@dataclass
class Section:
    name: str
    rom_offset: int | None
    org: int
    data: bytearray = field(default_factory=bytearray)

    @property
    def end(self) -> int:
        return self.org + len(self.data)


def _split_operands(s: str) -> list[str]:
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def _norm(op: str) -> str:
    o = op.strip().lower().replace(" ", "")
    o = o.replace("(", "[").replace(")", "]") if o.startswith("(") and o.endswith(")") else o
    return {"[hli]": "[hl+]", "[hld]": "[hl-]", "[$ff00+c]": "[c]", "[0xff00+c]": "[c]"}.get(o, o)


class Assembler:
    def __init__(self, symbols: dict[str, int] | None = None) -> None:
        self.symbols: dict[str, int] = dict(symbols or {})
        self.sections: list[Section] = []

    # -- expressions -------------------------------------------------------
    def _expr(self, text: str, scope: str, final: bool) -> int:
        t = text.strip()
        t = re.sub(r"\$([0-9A-Fa-f]+)", r"0x\1", t)
        t = re.sub(r"(?<![\w.])%([01]+)", r"0b\1", t)
        t = re.sub(r"(?<![\w])\.([A-Za-z_]\w*)", lambda m: f"{scope}__{m.group(1)}", t)
        t = t.replace(".", "__")
        env = {k.replace(".", "__"): v for k, v in self.symbols.items()}
        env.update(low=lambda v: v & 0xFF, high=lambda v: (v >> 8) & 0xFF)
        try:
            return int(eval(t, {"__builtins__": {}}, env))  # noqa: S307 - trusted build input
        except NameError:
            if final:
                raise AsmError(f"undefined symbol in '{text}'")
            return 0

    # -- encoding ----------------------------------------------------------
    def _encode(self, mn: str, ops: list[str], pc: int, scope: str, final: bool) -> list[int]:
        E = lambda s: self._expr(s, scope, final)  # noqa: E731
        n = [_norm(o) for o in ops]

        def mem_expr(o: str) -> str | None:
            if o.startswith("[") and o.endswith("]"):
                inner = o[1:-1]
                if inner not in ("hl", "bc", "de", "hl+", "hl-", "c"):
                    return inner
            return None

        def u8(v: int) -> int:
            if final and not -128 <= v <= 255:
                raise AsmError(f"byte out of range: {v}")
            return v & 0xFF

        def u16(v: int) -> list[int]:
            if final and not -32768 <= v <= 0xFFFF:
                raise AsmError(f"word out of range: {v}")
            return [v & 0xFF, (v >> 8) & 0xFF]

        if mn in SIMPLE and not ops:
            return list(SIMPLE[mn])
        if mn == "ld":
            d, s = n
            if d in R8 and s in R8:
                if d == s == "[hl]":
                    raise AsmError("ld [hl],[hl]")
                return [0x40 + 8 * R8[d] + R8[s]]
            if d in R16 and s not in R16 and not s.startswith(("sp+", "sp-")) and mem_expr(s) is None and not s.startswith("["):
                return [0x01 + 16 * R16[d]] + u16(E(ops[1]))
            if d == "sp" and s == "hl":
                return [0xF9]
            if d == "hl" and (s.startswith("sp+") or s.startswith("sp-")):
                v = E(ops[1].replace(" ", "")[2:])
                return [0xF8, v & 0xFF]
            if d == "a" and s in ("[bc]", "[de]", "[hl+]", "[hl-]", "[c]"):
                return [{"[bc]": 0x0A, "[de]": 0x1A, "[hl+]": 0x2A, "[hl-]": 0x3A, "[c]": 0xF2}[s]]
            if s == "a" and d in ("[bc]", "[de]", "[hl+]", "[hl-]", "[c]"):
                return [{"[bc]": 0x02, "[de]": 0x12, "[hl+]": 0x22, "[hl-]": 0x32, "[c]": 0xE2}[d]]
            if d == "a" and mem_expr(s) is not None:
                return [0xFA] + u16(E(ops[1].strip()[1:-1]))
            if s == "a" and mem_expr(d) is not None:
                return [0xEA] + u16(E(ops[0].strip()[1:-1]))
            if s == "sp" and mem_expr(d) is not None:
                return [0x08] + u16(E(ops[0].strip()[1:-1]))
            if d in R8:
                return [0x06 + 8 * R8[d], u8(E(ops[1]))]
            raise AsmError(f"bad ld {ops}")
        if mn == "ldh":
            d, s = n
            if (d, s) == ("a", "[c]"):
                return [0xF2]
            if (d, s) == ("[c]", "a"):
                return [0xE2]
            if d == "a":
                v = E(ops[1].strip()[1:-1])
                return [0xF0, v & 0xFF]
            v = E(ops[0].strip()[1:-1])
            return [0xE0, v & 0xFF]
        if mn in ("inc", "dec"):
            (o,) = n
            if o in R16:
                return [(0x03 if mn == "inc" else 0x0B) + 16 * R16[o]]
            return [(0x04 if mn == "inc" else 0x05) + 8 * R8[o]]
        if mn == "add" and n[0] == "hl":
            return [0x09 + 16 * R16[n[1]]]
        if mn == "add" and n[0] == "sp":
            return [0xE8, E(ops[1]) & 0xFF]
        if mn in ALU:
            if len(n) == 2:
                if n[0] != "a":
                    raise AsmError(f"bad {mn} {ops}")
                n, ops = n[1:], ops[1:]
            (o,) = n
            if o in R8:
                return [0x80 + 8 * ALU[mn] + R8[o]]
            return [0xC6 + 8 * ALU[mn], u8(E(ops[0]))]
        if mn in ("push", "pop"):
            return [(0xC5 if mn == "push" else 0xC1) + 16 * R16_STK[n[0]]]
        if mn == "jp":
            if n == ["hl"] or n == ["[hl]"]:
                return [0xE9]
            if len(n) == 2:
                return [0xC2 + 8 * COND[n[0]]] + u16(E(ops[1]))
            return [0xC3] + u16(E(ops[0]))
        if mn == "call":
            if len(n) == 2:
                return [0xC4 + 8 * COND[n[0]]] + u16(E(ops[1]))
            return [0xCD] + u16(E(ops[0]))
        if mn == "ret" and len(n) == 1:
            return [0xC0 + 8 * COND[n[0]]]
        if mn == "jr":
            tgt = E(ops[-1])
            off = tgt - (pc + 2)
            if final and not -128 <= off <= 127:
                raise AsmError(f"jr out of range ({off}) to {ops[-1]}")
            op = 0x18 if len(n) == 1 else 0x20 + 8 * COND[n[0]]
            return [op, off & 0xFF]
        if mn == "rst":
            return [0xC7 + (E(ops[0]) & 0x38)]
        if mn in CBOPS:
            return [0xCB, 8 * CBOPS[mn] + R8[n[0]]]
        if mn in BITOPS:
            b = E(ops[0])
            return [0xCB, BITOPS[mn] + 8 * b + R8[n[1]]]
        raise AsmError(f"unknown instruction {mn} {ops}")

    # -- driver ------------------------------------------------------------
    def _pass(self, lines: list[tuple[str, int, str]], final: bool) -> None:
        self.sections = []
        sec: Section | None = None
        scope = ""
        for src, lineno, raw in lines:
            line = raw.split(";", 1)[0].rstrip()
            if not line.strip():
                continue
            try:
                m = re.match(r"^\s*([.A-Za-z_][\w.]*):(.*)$", line)
                if m:
                    name = m.group(1)
                    if name.startswith("."):
                        name = f"{scope}.{name[1:]}"
                    else:
                        scope = name
                    if sec is None:
                        raise AsmError("label outside section")
                    addr = sec.end
                    if not final and name in self._defined_p1:
                        raise AsmError(f"duplicate label {name}")
                    self._defined_p1.add(name)
                    self.symbols[name] = addr
                    line = m.group(2)
                    if not line.strip():
                        continue
                m = re.match(r"^\s*([A-Za-z_]\w*)\s+equ\s+(.+)$", line, re.I)
                if m:
                    self.symbols[m.group(1)] = self._expr(m.group(2), scope, final)
                    continue
                parts = line.strip().split(None, 1)
                mn = parts[0].lower()
                rest = parts[1] if len(parts) > 1 else ""
                if mn == "section":
                    a = _split_operands(rest)
                    off = None if a[1].strip().lower() == "none" else self._expr(a[1], scope, True)
                    sec = Section(a[0].strip(), off, self._expr(a[2], scope, True))
                    self.sections.append(sec)
                    continue
                if sec is None:
                    raise AsmError("code outside section")
                if mn == "db":
                    for item in _split_operands(rest):
                        if item.startswith('"'):
                            sec.data.extend(item.strip('"').encode("ascii"))
                        else:
                            sec.data.append(self._expr(item, scope, final) & 0xFF)
                    continue
                if mn == "dw":
                    for item in _split_operands(rest):
                        v = self._expr(item, scope, final)
                        sec.data.extend([v & 0xFF, (v >> 8) & 0xFF])
                    continue
                if mn == "ds":
                    a = _split_operands(rest)
                    cnt = self._expr(a[0], scope, True)
                    fill = self._expr(a[1], scope, True) if len(a) > 1 else 0
                    sec.data.extend([fill & 0xFF] * cnt)
                    continue
                if mn == "align":
                    al = self._expr(rest, scope, True)
                    while sec.end % al:
                        sec.data.append(0xFF)
                    continue
                sec.data.extend(self._encode(mn, _split_operands(rest), sec.end, scope, final))
            except AsmError as exc:
                raise AsmError(f"{src}:{lineno}: {exc}: {raw.strip()}") from None
            except Exception as exc:  # pragma: no cover - diagnostics
                raise AsmError(f"{src}:{lineno}: {type(exc).__name__}: {exc}: {raw.strip()}") from None

    def assemble(self, sources: list[tuple[str, str]]) -> list[Section]:
        lines = [(name, i + 1, l) for name, text in sources for i, l in enumerate(text.splitlines())]
        self._defined_p1: set[str] = set()
        self._pass(lines, final=False)
        self._defined_p1 = set(self.symbols)  # allow redefinition in pass 2
        self._pass(lines, final=True)
        return self.sections


def assemble(sources: list[tuple[str, str]], symbols: dict[str, int] | None = None) -> tuple[list[Section], dict[str, int]]:
    a = Assembler(symbols)
    secs = a.assemble(sources)
    return secs, a.symbols
