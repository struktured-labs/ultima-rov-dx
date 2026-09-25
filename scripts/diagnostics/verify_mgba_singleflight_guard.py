#!/usr/bin/env python3
"""Hardware-free regression for the project mGBA safety boundary.

Condensed port of penta-dragon-dx's verifier: checks the guard components
exist, the agent PreToolUse hook blocks raw emulator launches, and the
single-flight lock fails closed (exit 75) using the guard's `self-test`
mode (which execs /bin/sleep, never an emulator).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "scripts/mgba_singleflight.py"
COMPONENTS = (
    GUARD,
    ROOT / "scripts/mgba-qt-singleflight",
    ROOT / "scripts/mgba-headless-singleflight",
    ROOT / "scripts/launch_mgba.sh",
    ROOT / "scripts/hooks/guard_mgba_launch.py",
    ROOT / ".githooks/pre-commit",
)
HOOK = ROOT / "scripts/hooks/guard_mgba_launch.py"

MUST_BLOCK = (
    "mgba-qt rom/working/ultima_rov_dx.gb",
    "/usr/games/mgba-qt x.gb",
    "xvfb-run -a mgba-headless x.gb",
    "echo hi; mgba x.gb",
    "python3 some_probe.py --mgba /usr/games/mgba-qt",
)
MUST_ALLOW = (
    "scripts/launch_mgba.sh rom/working/ultima_rov_dx.gb",
    "python3 scripts/build_dx.py",
    "python3 probe.py --mgba scripts/mgba-headless-singleflight",
    "ls docs/mgba_notes.md",
)


def hook_status(command: str) -> int:
    event = {"tool_name": "Bash", "tool_input": {"command": command}}
    return subprocess.run(
        [sys.executable, str(HOOK)], input=json.dumps(event), text=True,
        capture_output=True, check=False, timeout=5,
    ).returncode


def main() -> int:
    failures: list[str] = []
    for path in COMPONENTS:
        if not path.is_file() or not os.access(path, os.X_OK):
            failures.append(f"missing or non-executable guard component: {path}")
    for command in MUST_BLOCK:
        if hook_status(command) != 2:
            failures.append(f"hook did not block: {command!r}")
    for command in MUST_ALLOW:
        if hook_status(command) != 0:
            failures.append(f"hook wrongly blocked: {command!r}")

    with tempfile.TemporaryDirectory(dir=ROOT / "tmp" if (ROOT / "tmp").is_dir() else None) as scratch:
        env = dict(os.environ, ROV_MGBA_LOCK=str(Path(scratch) / "lock"))
        owner = subprocess.Popen([sys.executable, str(GUARD), "self-test", "5"], env=env)
        try:
            deadline = time.monotonic() + 3
            lock = Path(env["ROV_MGBA_LOCK"])
            while time.monotonic() < deadline and f"pid={owner.pid}" not in (lock.read_text() if lock.exists() else ""):
                time.sleep(0.02)
            second = subprocess.run([sys.executable, str(GUARD), "self-test", "0"], env=env,
                                    capture_output=True, text=True, timeout=5)
            if second.returncode != 75:
                failures.append(f"second guarded launch returned {second.returncode}, expected 75")
        finally:
            owner.terminate()
            owner.wait(timeout=5)

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print("PASS: mGBA single-flight guard, agent hook, and fail-closed lock verified (no emulator launched).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
