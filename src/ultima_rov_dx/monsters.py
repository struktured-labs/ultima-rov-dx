"""Monster templates of Ultima: Runes of Virtue and their colour tiers.

Every spawned object comes from a 9-byte template (reverse_engineering/notes/
monsters.md): bank 1 ``$55AF + 9 * U`` where U = type (0-66) for the first
object group of an area and 67 + type for the second ("alt") group, which the
game reads from ``$580A`` (= ``$55AF + 9 * 67``). Bytes: 0 count, 1 graphic
(bit 7 large, bit 6 people bank, bits 1-5 index), 2 flags, 3 HP, 4 behaviour,
5 contact damage (``>= $78``: no contact damage / talk id), 6-8 misc.

The same graphic is reused with different stats (green / red slimes...).
``tiers`` ranks those variants per graphic so the runtime can colour a record
by its template (base / stronger / strongest OBJ palette), never by area.
"""

from __future__ import annotations

from dataclasses import dataclass

TEMPLATE_BANK = 1
TEMPLATE_ADDR = 0x55AF
TEMPLATE_LEN = 9
NORMAL_TYPES = 67            # $55AF..$5809; the alt table at $580A follows directly
ALT_TYPES = 0x48             # area list types $00-$47 are templates ($48-$67 floor items)
COUNT = NORMAL_TYPES + ALT_TYPES
NO_CONTACT = 0x78            # damage byte >= $78: special object / talk id, not a hit
MAX_TIERS = 3
DMG_STEP = 1.4               # a variant group starts at 1.4x the damage (and DMG_MIN more) ...
DMG_MIN = 4
HP_STEP = 4                  # ... or 4x the HP of the group's weakest member


@dataclass(frozen=True)
class Template:
    index: int               # U
    count: int
    gfx: int
    flags: int
    hp: int
    behaviour: int
    damage: int

    @property
    def name(self) -> str:
        return f"A{self.index:02X}" if self.index < NORMAL_TYPES else f"B{self.index - NORMAL_TYPES:02X}"

    @property
    def key(self) -> int:
        """Graphic identity (OBJPAL key): bit 7 (large) and bit 0 cleared."""
        return self.gfx & 0x7E

    @property
    def large(self) -> bool:
        return bool(self.gfx & 0x80)

    @property
    def hostile(self) -> bool:
        return self.damage < NO_CONTACT and self.hp > 1


def templates(rom: bytes) -> list[Template]:
    base = TEMPLATE_BANK * 0x4000 + (TEMPLATE_ADDR - 0x4000)
    out = []
    for u in range(COUNT):
        b = rom[base + TEMPLATE_LEN * u: base + TEMPLATE_LEN * (u + 1)]
        out.append(Template(u, b[0], b[1], b[2], b[3], b[4], b[5]))
    return out


def tiers(temps: list[Template], tiered_keys: set[int]) -> dict[int, int]:
    """Template index -> tier 0-2 for graphics in ``tiered_keys``.

    Per graphic, the distinct (damage, HP) pairs of hostile templates are
    sorted; a new group starts when damage reaches DMG_STEP x (and at least
    DMG_MIN more) or HP reaches
    HP_STEP x the first pair of the current group. Groups past MAX_TIERS
    merge into the last. Non-hostile templates (no contact damage, 1 HP
    projectiles) and graphics with one group stay tier 0.
    """
    out = {t.index: 0 for t in temps}
    by_key: dict[int, set[tuple[int, int]]] = {}
    for t in temps:
        if t.key in tiered_keys and t.hostile:
            by_key.setdefault(t.key, set()).add((t.damage, t.hp))
    group_of: dict[tuple[int, tuple[int, int]], int] = {}
    for key, pairs in by_key.items():
        g, base = 0, None
        for dmg, hp in sorted(pairs):
            if base is not None and ((dmg >= DMG_STEP * base[0] and dmg >= base[0] + DMG_MIN) or hp >= HP_STEP * base[1]):
                g, base = g + 1, (dmg, hp)
            if base is None:
                base = (dmg, hp)
            group_of[(key, (dmg, hp))] = min(g, MAX_TIERS - 1)
    for t in temps:
        if t.key in tiered_keys and t.hostile:
            out[t.index] = group_of[(t.key, (t.damage, t.hp))]
    return out


def tier_table(temps: list[Template], tier: dict[int, int]) -> bytes:
    """Nibble per template (low nibble = even U): the tier 0-2."""
    nib = [tier[t.index] for t in temps]
    nib += [0] * (len(nib) & 1)
    return bytes(nib[i] | nib[i + 1] << 4 for i in range(0, len(nib), 2))
