"""Location and identity of the user-supplied original ROM.

The original ROM is copyrighted and is never stored in this repository
(``*.gb`` is gitignored). Supply your own dump at ``ORIGINAL_ROM_PATH``.

Known-good hashes come from the No-Intro Game Boy DAT (via the
libretro-database mirror, DAT version 2026.08.01) and are independently
listed by TASVideos. See ``docs/rom_facts.md`` for citations. Do not edit
these values without citing a source.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import zlib

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Filename follows the No-Intro naming for the supported dump.
ORIGINAL_ROM_NAME = "Ultima - Runes of Virtue (USA).gb"
ORIGINAL_ROM_PATH = PROJECT_ROOT / "rom" / ORIGINAL_ROM_NAME

# Optional override (absolute path), e.g. for a ROM kept outside the repo.
ROM_ENV_VAR = "ULTIMA_ROV_ROM"

# sysexits.h EX_NOINPUT / EX_DATAERR -- matches the sysexits style used by
# the mGBA single-flight guard (64/69/70/75).
EXIT_ROM_MISSING = 66
EXIT_ROM_MISMATCH = 65


@dataclass(frozen=True)
class KnownDump:
    name: str
    size: int
    crc32: str
    md5: str
    sha1: str
    supported: bool
    note: str = ""


KNOWN_DUMPS: tuple[KnownDump, ...] = (
    KnownDump(
        name="Ultima - Runes of Virtue (USA)",
        size=131072,
        crc32="C44A0F1E",
        md5="411C3D168141D10EDDD93243F2A7765F",
        sha1="8D911CBBC6BD1518A85282DEF7F01D3ADD16E596",
        supported=True,
    ),
    KnownDump(
        name="Ultima - Ushinawareta Runes (Japan)",
        size=131072,
        crc32="D2F94181",
        md5="DD519F58F68E27B70C29CF19500A0154",
        sha1="3A1D88736E13436CDE15029DADD951B0B1C637E5",
        supported=False,
        note="Japanese release; not targeted (all RE work assumes the USA dump).",
    ),
    KnownDump(
        name="Ultima - Runes of Virtue II (USA)",
        size=262144,
        crc32="C449FBBF",
        md5="15CD267D7805FE9F1769E9644A9CEC2E",
        sha1="99C4FBF832EDB9B58960EC744AE784B55C7D63D2",
        supported=False,
        note="This is the sequel, not Runes of Virtue (I).",
    ),
)

SUPPORTED_DUMP = next(d for d in KNOWN_DUMPS if d.supported)


class RomError(Exception):
    """Raised with a human-readable explanation and an exit status."""

    def __init__(self, message: str, status: int):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class RomIdentity:
    path: Path
    size: int
    crc32: str
    md5: str
    sha1: str
    sha256: str
    match: KnownDump | None


def default_rom_path() -> Path:
    override = os.environ.get(ROM_ENV_VAR)
    return Path(override) if override else ORIGINAL_ROM_PATH


def missing_rom_message(path: Path) -> str:
    return (
        "ERROR: original ROM not found.\n"
        f"  expected: {path}\n"
        f"  supported dump: {SUPPORTED_DUMP.name} ({SUPPORTED_DUMP.size} bytes)\n"
        f"    MD5  {SUPPORTED_DUMP.md5.lower()}\n"
        f"    SHA1 {SUPPORTED_DUMP.sha1.lower()}\n"
        f"    CRC32 {SUPPORTED_DUMP.crc32.lower()}\n"
        "Copy your own legally obtained dump to that exact path (it is gitignored),\n"
        f"or set {ROM_ENV_VAR}=/absolute/path/to/rom.gb. This project never downloads ROMs."
    )


def identify(path: Path) -> RomIdentity:
    data = path.read_bytes()
    crc = f"{zlib.crc32(data) & 0xFFFFFFFF:08X}"
    md5 = hashlib.md5(data).hexdigest().upper()
    sha1 = hashlib.sha1(data).hexdigest().upper()
    sha256 = hashlib.sha256(data).hexdigest()
    match = next((d for d in KNOWN_DUMPS if d.md5 == md5 and d.sha1 == sha1), None)
    return RomIdentity(path, len(data), crc, md5, sha1, sha256, match)


def require_original_rom(path: Path | None = None) -> tuple[Path, bytes]:
    """Return (path, bytes) of the verified original ROM or raise RomError."""

    path = Path(path) if path else default_rom_path()
    if not path.is_file():
        raise RomError(missing_rom_message(path), EXIT_ROM_MISSING)
    ident = identify(path)
    if ident.match is None:
        raise RomError(
            f"ERROR: {path} does not match any known dump.\n"
            f"  got      size={ident.size} md5={ident.md5.lower()} sha1={ident.sha1.lower()}\n"
            f"  expected size={SUPPORTED_DUMP.size} md5={SUPPORTED_DUMP.md5.lower()} "
            f"sha1={SUPPORTED_DUMP.sha1.lower()}\n"
            "Headered, trimmed, patched, or bad dumps are not supported.",
            EXIT_ROM_MISMATCH,
        )
    if not ident.match.supported:
        raise RomError(
            f"ERROR: {path} is '{ident.match.name}', which is not supported. "
            f"{ident.match.note}",
            EXIT_ROM_MISMATCH,
        )
    return path, path.read_bytes()
