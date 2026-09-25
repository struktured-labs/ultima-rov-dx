#!/usr/bin/env python3
"""Claude PreToolUse hook: reject raw/bypass mGBA shell launches."""

from __future__ import annotations

import json
import re
import sys


RAW_EMULATOR = re.compile(
    r"(?:(?<=^)|(?<=[\s;&|()]))"
    r"(?:/[^\s;&|()]*/)?"
    r"(?:mgba|mgba-qt|mgba-headless)"
    r"(?=$|[\s;&|()])",
)
UNSAFE_OVERRIDE = re.compile(
    r"--mgba(?:=|\s+)(?![^\s]*mgba-(?:qt|headless)-singleflight)"
)
UNMIGRATED_ENTRYPOINTS: tuple[str, ...] = (
    # Add legacy scripts here that launch mGBA without the single-flight guard.
)


def invokes_unmigrated_entrypoint(command: str) -> str | None:
    runner = r"(?:python(?:3)?|uv\s+run\s+python(?:3)?|bash|sh)"
    for name in UNMIGRATED_ENTRYPOINTS:
        pattern = rf"(?:^|[\s;&|]){runner}\s+[^\s;&|]*{re.escape(name)}(?=$|[\s;&|])"
        if re.search(pattern, command):
            return name
    return None


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        print("mGBA safety hook could not parse its event input", file=sys.stderr)
        return 2

    if event.get("tool_name") != "Bash":
        return 0
    command = str(event.get("tool_input", {}).get("command", ""))
    legacy = invokes_unmigrated_entrypoint(command)
    if RAW_EMULATOR.search(command) or UNSAFE_OVERRIDE.search(command) or legacy:
        legacy_reason = (
            f" {legacy} is a quarantined legacy launcher and must be migrated "
            "before use."
            if legacy
            else ""
        )
        print(
            "BLOCKED by project mGBA safety policy: raw emulator commands and "
            "unguarded --mgba overrides are forbidden. Use "
            "scripts/launch_mgba.sh for headed play, or the default guarded "
            "verification scripts. Only one emulator may run at a time."
            f"{legacy_reason}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
