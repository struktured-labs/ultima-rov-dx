#!/usr/bin/env python3
"""Pre-commit policy: never commit ROMs, saves, or emulator states; keep sources compiling.

Simplified from penta-dragon-dx's verify_precommit_policy.py (which also
requires a hash-bound emulator receipt for production changes -- add that
here once a verification suite exists).
"""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN = re.compile(r"\.(gb|gbc|gba|sgb|sav|srm|ram|rtc|ss\d*|state\d*|bps|ups)$", re.I)
ALLOWED_BINARIES = {Path("rom/ultima_rov_dx.ips")}  # ROM-free distribution patch


def staged_paths() -> list[Path]:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    return [Path(line) for line in out.splitlines() if line.strip()]


def main() -> int:
    staged = staged_paths()
    forbidden = [p for p in staged if FORBIDDEN.search(p.name) and p not in ALLOWED_BINARIES]
    if forbidden:
        print("FAIL: ROM/save/state artifacts are staged: " + ", ".join(map(str, forbidden)))
        return 1
    big = [p for p in staged if (ROOT / p).is_file() and (ROOT / p).stat().st_size > 5 * 1024 * 1024]
    if big:
        print("FAIL: files over 5 MiB are staged (use tmp/ or /mnt/data/tmp/): " + ", ".join(map(str, big)))
        return 1
    status = subprocess.run(
        [sys.executable, "-m", "compileall", "-q", "src", "scripts", "tests"], cwd=ROOT, check=False
    ).returncode
    if status:
        return status
    print("PASS: no ROM/save/state artifacts staged; sources compile.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
