"""Game-specific facts about Ultima: Runes of Virtue (USA).

EVERY value here must come from reverse engineering the verified original
ROM (see reverse_engineering/notes/TODO.md) and should cite the doc or probe
that established it. Nothing has been established yet: the ROM has not been
supplied. ``None`` means "unknown -- do not guess".

Nothing in this file was copied from penta-dragon-dx; Penta Dragon's
addresses (VBlank chain at $06D1, inline copier at bank1:$42A7, HRAM
FFC1/FFC4, D880, ...) are meaningless for this game.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Hook:
    """A patch site: replace ``length`` bytes at file ``offset`` with a CALL/JP."""

    name: str
    offset: int | None       # file offset in the original ROM
    preimage: bytes | None   # exact original bytes expected at offset
    note: str


# TODO(RE): cartridge header facts, to be filled in from `rov-dx check-rom`
# output once the ROM is present (do not fill from memory or forums).
CARTRIDGE_TYPE: int | None = None      # header 0x147 (battery saves suggest MBCx+RAM+BATTERY; unverified)
ROM_BANKS: int | None = None           # 131072 bytes per No-Intro -> 8 x 16 KiB banks (confirm)
BANK_SELECT_SHADOW: int | None = None  # WRAM/HRAM byte where the game mirrors its current ROM bank

# TODO(RE): where CGB palettes get loaded once after LCD init (before the
# title screen draws). Without this the CGB-flagged ROM shows a blank/white
# screen, because CGB mode ignores BGP/OBP0/OBP1.
PALETTE_INIT_HOOK = Hook("palette_init", None, None, "after LCD init, before title")

# TODO(RE): VBlank handler entry (vector $0040 target) for per-scene
# palette/attribute service.
VBLANK_HOOK = Hook("vblank", None, None, "VBlank ISR chain")

# TODO(RE): BG tilemap writers (dungeon/overworld map redraw, text boxes,
# status bar) -- needed for per-tile BG attributes in VRAM bank 1.
TILEMAP_WRITER_HOOKS: tuple[Hook, ...] = ()

# TODO(RE): shadow-OAM buffer address and the DMA routine in HRAM
# (for OBJ palette bits 0-2 in OAM attributes).
SHADOW_OAM: int | None = None
OAM_DMA_HRAM: int | None = None

# TODO(RE): scene/state variables (title, character select, overworld,
# dungeon number 1..8, shrine, 2-player mode, ending) for scene-aware palettes.
SCENE_STATE_ADDR: int | None = None

# TODO(RE): free space usable for injected code/data (run `rov-dx analyze`).
FREE_SPACE: tuple[tuple[int, int], ...] = ()   # (file_offset, length)


def missing_facts() -> list[str]:
    """Names of facts the production builder needs but that are still unknown."""

    missing = []
    if CARTRIDGE_TYPE is None:
        missing.append("CARTRIDGE_TYPE")
    if PALETTE_INIT_HOOK.offset is None or PALETTE_INIT_HOOK.preimage is None:
        missing.append("PALETTE_INIT_HOOK")
    if not FREE_SPACE:
        missing.append("FREE_SPACE")
    return missing
