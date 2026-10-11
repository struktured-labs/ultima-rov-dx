"""Natural creature colours and the per-area OBJ palette allocation.

Rule (Carmelo, Oct 2026): every creature type has its own natural colour,
the same in every area; only where the game has a tougher version of the
same sprite does the colour change to mark it (reverse_engineering/notes/
monsters.md "Colours").

The CGB has 8 OBJ palettes: 0 is the player and 7 the wand fire / OBP1, so
1-6 are filled per area. A *class* is one colour: a creature tier
(``rov_palettes.yaml`` ``creatures``: base colour + ``variants``) or one of
the shared categories ``folk`` / ``royal`` / ``item`` (``obj_categories.yaml``
ids, colours from ``obj_palettes``). Class ids are 1-based; the tiers of a
creature are consecutive ids, so its colours are consecutive in
``class_col`` and a block of palettes p, p+1, p+2 holds tiers 0, 1, 2 (the
runtime adds the record's tier to the base palette, dx.asm ``TierPal``).

``allocate`` is the Python model of the bank-9 runtime ``NatAssign9``: the
classes of the loaded sprite slots in slot order (plus ``folk`` on surface
maps, for the ship), each tiered creature widened to a block reaching its
highest tier in the area's object list while palettes are left, then packed
from palette 1. More than 6 classes: the extra ones share the palette of
their nearest-coloured loaded class (``fallback``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import monsters as MON
from . import palettes as P

MAX_CLASSES = 64          # dx.asm NAT_CLASSES (class ids 1-63, 0 = none)
FIRST_PAL, LAST_PAL = 1, 6
FALLBACKS = 3             # bytes per class in the fallback table
LIST_ADDR, LIST_END = 0xC5C0, 0xC600
FLOOR_TYPES = 0x48        # area list types >= $48 are floor items, not templates
SHARED = ("folk", "royal", "item")


class CreatureError(Exception):
    pass


def _enc(cols: list[str], what: str) -> bytes:
    if not isinstance(cols, list) or len(cols) != 4:
        raise CreatureError(f"{what}: need 4 colours")
    return b"".join(P.bgr555(c).to_bytes(2, "little") for c in cols)


def _rgb(c: int) -> tuple[int, int, int]:
    return (c & 31, (c >> 5) & 31, (c >> 10) & 31)


@dataclass
class Creatures:
    names: list[str] = field(default_factory=list)       # class id - 1 -> "troll", "troll+1", "folk"...
    key_class: bytes = bytes(64)                          # key >> 1 -> base class id
    class_tiers: bytes = bytes(MAX_CLASSES)               # base class id -> tiers (1-3); 0 for variants
    class_col: bytes = bytes(8 * MAX_CLASSES)             # class id -> 4 BGR555 colours
    tpl: bytes = b""                                      # template U -> tier << 6 | base class (tier >= 1 only)
    fallback: bytes = bytes(FALLBACKS * MAX_CLASSES)      # base class id -> nearest-coloured base classes
    folk: int = 0                                         # class of the ship (surface maps)
    tiered_keys: frozenset = frozenset()
    tiers: dict = field(default_factory=dict)             # template index -> tier (monsters.tiers)

    def cls(self, name: str) -> int:
        return self.names.index(name) + 1

    def class_of_key(self, key: int) -> int:
        return self.key_class[(key & 0x7E) >> 1]


def build(pal_data: dict[str, Any], obj_cat: dict[str, Any], temps: list[MON.Template]) -> Creatures:
    spec = pal_data.get("creatures") or {}
    if not spec:
        raise CreatureError("rov_palettes.yaml: no `creatures`")
    if pal_data.get("obj_themes"):
        raise CreatureError("obj_themes: creatures keep one colour everywhere (no per-area tint)")
    for k in ("tier_palettes", "knight_borrow"):
        if obj_cat.get(k) is not None:
            raise CreatureError(f"obj_categories.yaml `{k}` is gone: see rov_palettes.yaml `creatures`")
    cr = Creatures()
    names: list[str] = []
    cols = bytearray(8)                                   # class 0: none
    tiers_of: dict[int, int] = {}
    key_owner: dict[int, str] = {}
    creature_keys: dict[str, list[int]] = {}
    for name, ent in spec.items():
        ids = ent.get("ids") or []
        if not ids:
            raise CreatureError(f"creatures.{name}: no ids")
        for k in ids:
            if not 0 <= k < 0x80 or k & 1:
                raise CreatureError(f"creatures.{name}: id {k:#x} must be even and < $80")
            if k in key_owner:
                raise CreatureError(f"creatures.{name}: id {k:#x} also in {key_owner[k]}")
            key_owner[k] = name
        creature_keys[name] = list(ids)
        base = len(names) + 1
        variants = ent.get("variants") or []
        names.append(name)
        cols += _enc(ent.get("colors"), f"creatures.{name}")
        for i, v in enumerate(variants):
            names.append(f"{name}+{i + 1}")
            cols += _enc(v.get("colors"), f"creatures.{name}.variants[{i}]")
        tiers_of[base] = 1 + len(variants)
        if len(variants) > MON.MAX_TIERS - 1:
            raise CreatureError(f"creatures.{name}: at most {MON.MAX_TIERS - 1} variants")
    obj_names = P.names(pal_data, "obj_palettes")
    ids = obj_cat.get("ids") or {}
    for cat in ids:
        if cat not in SHARED:
            raise CreatureError(f"obj_categories ids.{cat}: only {SHARED} (creatures live in rov_palettes.yaml)")
    for cat in SHARED:
        if cat not in obj_names:
            raise CreatureError(f"obj_palettes has no {cat!r}")
        base = len(names) + 1
        names.append(cat)
        cols += _enc(pal_data["obj_palettes"][cat]["colors"], f"obj_palettes.{cat}")
        tiers_of[base] = 1
        for k in ids.get(cat) or []:
            if not 0 <= k < 0x80 or k & 1:
                raise CreatureError(f"ids.{cat}: id {k:#x} must be even and < $80")
            if k in key_owner:
                raise CreatureError(f"ids.{cat}: id {k:#x} also in {key_owner[k]}")
            key_owner[k] = cat
    if len(names) >= MAX_CLASSES:
        raise CreatureError(f"too many colour classes ({len(names)} >= {MAX_CLASSES})")
    for k in ("default", "ship"):
        if obj_cat.get(k) not in names:
            raise CreatureError(f"obj_categories `{k}`: {obj_cat.get(k)!r} is not a class")
    default = names.index(obj_cat["default"]) + 1
    kc = bytearray([default] * 64)
    for k, name in key_owner.items():
        kc[k >> 1] = names.index(name) + 1
    cr.names, cr.key_class = names, bytes(kc)
    ct = bytearray(MAX_CLASSES)
    for c, n in tiers_of.items():
        ct[c] = n
    cr.class_tiers = bytes(ct)
    cr.class_col = bytes(cols) + bytes(8 * MAX_CLASSES - len(cols))
    cr.folk = names.index(obj_cat["ship"]) + 1
    # tiers from the ROM (monsters.tiers) over every creature graphic; a creature
    # with variants needs exactly that many tiers, one without needs one
    ckeys = {k for ks in creature_keys.values() for k in ks}
    tier = MON.tiers(temps, ckeys)
    for name, ks in creature_keys.items():
        found = {tier[t.index] for t in temps if t.key in ks}
        want = tiers_of[names.index(name) + 1]
        if max(found | {0}) + 1 != want:
            raise CreatureError(f"creatures.{name}: the ROM has {max(found | {0}) + 1} tier(s), "
                                f"the table {want} (base + variants)")
        if want > 1 and len({t.key for t in temps if t.key in ks}) != 1:
            raise CreatureError(f"creatures.{name}: a creature with variants must have one graphic with templates")
    cr.tiered_keys = frozenset(k for name, ks in creature_keys.items() for k in ks
                               if tiers_of[names.index(name) + 1] > 1)
    cr.tiers = tier
    tpl = bytearray(len(temps))
    for t in temps:
        if t.key in cr.tiered_keys and tier[t.index]:
            tpl[t.index] = tier[t.index] << 6 | cr.class_of_key(t.key)
    cr.tpl = bytes(tpl)
    # fallback: base classes ranked by colour distance (light + mid shade)
    bases = [c for c in range(1, len(names) + 1) if ct[c]]

    def col(c: int) -> list[tuple[int, int, int]]:
        return [_rgb(int.from_bytes(cr.class_col[8 * c + 2 * s:8 * c + 2 * s + 2], "little")) for s in (1, 2, 3)]

    fb = bytearray(FALLBACKS * MAX_CLASSES)
    for c in bases:
        a = col(c)
        rank = sorted((sum((x - y) ** 2 for p, q in zip(a, col(o)) for x, y in zip(p, q)), o) for o in bases if o != c)
        for i, (_, o) in enumerate(rank[:FALLBACKS]):
            fb[FALLBACKS * c + i] = o
    cr.fallback = bytes(fb)
    return cr


@dataclass
class Allocation:
    order: list[int]                       # base classes in allocation order
    need: dict[int, int]                   # base class -> tiers wanted (highest tier in the area + 1)
    size: dict[int, int]                   # base class -> palettes given (1 = variants share the base)
    pal: dict[int, int]                    # base class -> first OBJ palette
    shared: set[int]                       # classes without a palette of their own (overflow)
    objpal: dict[int, int]                 # loaded key -> OBJPAL byte (palette | $80 when tiered)
    colors: dict[int, bytes]               # OBJ palette -> 8 bytes, palettes the area owns
    ship_pal: int | None = None


def allocate(cr: Creatures, slots: list[int], count: int, area_list: list[tuple[int, int]] = (),
             c508: int = 0xFF, surface: bool = False) -> Allocation:
    """``slots`` = $C580.., ``count`` = $C539, ``area_list`` = ($C5C0 pairs
    up to the 0 type byte), ``c508`` = [$C508] (first alt-group entry, low
    byte), ``surface`` = MAP_THEME 0 (ship)."""
    n = min(count, 16)
    order: list[int] = []
    need: dict[int, int] = {}
    keys: list[int] = []
    for g in slots[:n]:
        if g == 0xFF:
            continue
        k = g & 0x7E
        keys.append(k)
        c = cr.class_of_key(k)
        if c not in need:
            need[c] = 1
            order.append(c)
    if surface and cr.folk not in need:
        need[cr.folk] = 1
        order.append(cr.folk)
    for i, (_pos, t) in enumerate(area_list):
        if LIST_ADDR + 2 * i >= LIST_END or t == 0:
            break
        ty = t & 0x7F
        if ty >= FLOOR_TYPES:
            continue
        u = ty + (MON.NORMAL_TYPES if ((LIST_ADDR + 2 * i) & 0xFF) >= c508 else 0)
        v = cr.tpl[u]
        if v:
            c, tr = v & 0x3F, v >> 6
            if c in need:
                need[c] = max(need[c], tr + 1)
    size = {c: 1 for c in order}
    spare = LAST_PAL - FIRST_PAL + 1 - len(order)
    for c in order:
        extra = need[c] - 1
        if 0 < extra <= spare:
            size[c] = need[c]
            spare -= extra
    pal: dict[int, int] = {}
    shared: set[int] = set()
    p = FIRST_PAL
    for c in order:
        if p + size[c] - 1 <= LAST_PAL:
            pal[c] = p
            p += size[c]
        else:
            size[c] = 1
            shared.add(c)
    for c in order:
        if c in shared:
            fb = [f for f in cr.fallback[FALLBACKS * c:FALLBACKS * c + FALLBACKS] if f in pal]
            pal[c] = pal[fb[0]] if fb else FIRST_PAL
    objpal = {k: pal[cr.class_of_key(k)] | (0x80 if size[cr.class_of_key(k)] > 1 else 0) for k in keys}
    colors: dict[int, bytes] = {}
    for c in order:
        if c in shared:
            continue
        for t in range(size[c]):
            colors[pal[c] + t] = cr.class_col[8 * (c + t):8 * (c + t) + 8]
    return Allocation(order, need, size, pal, shared, objpal, colors, pal.get(cr.folk))


PARADE_PREF = (1, 2, 3, 4, 5, 6, 7, 0)   # 0 / 7 only when 1-6 are taken: the parade shows no player or OBP1 sprite


@dataclass
class ParadePlan:
    pal: bytes        # OBJ palette per list byte (PARADE_PAL_ROM; $FF terminators 0)
    colors: bytes     # 64 per page: colours of OBJ palette p at 8 x p (NAT_PARADE)
    plist: bytes      # 16 per page: the palettes the page loads, $FF-terminated (NAT_PLIST)
    pages: list       # per page: {class name: palette}
    loads: list       # per page: palettes written for it


def parade_plan(cr: Creatures, list_bytes: bytes) -> ParadePlan:
    """Attract-loop parade (bank 7 lists of 4 graphic bytes + $FF): each page
    shows its creatures in their natural (base) colours. Page k + 1 is loaded
    into CRAM while page k is still up (bank 9 ParadeStep9), so the palettes
    it writes are ones page k does not show; a class already in CRAM keeps its
    palette (nothing to write). The
    first page is loaded at the parade's LCD-on through BASE_OBJ: palettes 1-6."""
    pal, cols, plist, pages, loads = bytearray(), bytearray(), bytearray(), [], []
    cram: dict[int, int] = {}
    prev: set[int] = set()
    for k, i in enumerate(range(0, len(list_bytes), 5)):
        page = list_bytes[i:i + 5]
        classes: list[int] = []
        for b in page:
            if b != 0xFF:
                c = cr.class_of_key((b & 0x3F) | ((b & 0x80) >> 1))
                if c not in classes:
                    classes.append(c)
        allowed = [p for p in PARADE_PREF if p not in prev and (k or FIRST_PAL <= p <= LAST_PAL)]
        assign: dict[int, int] = {}
        for c in classes:                     # already showing / loaded: keep it (nothing to write)
            have = [p for p in PARADE_PREF if cram.get(p) == c and p not in assign.values()
                    and (k or FIRST_PAL <= p <= LAST_PAL)]
            if have:
                assign[c] = have[0]
        for c in classes:
            if c not in assign:
                free = [p for p in allowed if p not in assign.values() and cram.get(p) not in classes]
                if not free:
                    raise CreatureError(f"parade page {k}: {len(classes)} classes, no palette left")
                assign[c] = free[0]
        load = [assign[c] for c in classes if cram.get(assign[c]) != c or not k]
        if len(load) > 15:
            raise CreatureError("parade page loads too many palettes")
        block = bytearray(64)
        for c in classes:
            cram[assign[c]] = c
            block[8 * assign[c]:8 * assign[c] + 8] = cr.class_col[8 * c:8 * c + 8]
        for b in page:
            pal.append(0 if b == 0xFF else assign[cr.class_of_key((b & 0x3F) | ((b & 0x80) >> 1))])
        cols += block
        plist += bytes(load) + b"\xFF" + bytes(15 - len(load))
        pages.append({cr.names[c - 1]: p for c, p in assign.items()})
        loads.append(load)
        prev = set(assign.values())
    return ParadePlan(bytes(pal), bytes(cols), bytes(plist), pages, loads)
