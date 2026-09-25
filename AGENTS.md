# Project agent rules

## Scratch-artifact locations

- Never use the system `/tmp` directory for this project.
- Use the repository-local ignored `tmp/` directory for ordinary temporary
  builds, receipts, traces, screenshots, and other scratch artifacts.
- Use `/mnt/data/tmp/` for large scratch artifacts such as long videos,
  frame sequences, and bulky emulator corpora.
- If `/mnt/data/tmp/` is unavailable or not writable, keep the artifact in
  repository-local `tmp/`; never fall back to the system `/tmp` directory.
- Keep ROMs, save data, savestates, captures, and other generated scratch
  artifacts out of Git regardless of which scratch location owns them.

## Original ROM

- Never download, request, or commit a ROM. The user supplies
  `rom/Ultima - Runes of Virtue (USA).gb`; verify it with
  `python3 scripts/check_rom.py` before relying on it.
- Never record game facts (addresses, header values, hashes) that were not
  observed in the verified ROM or cited from a reputable source.

## Hard emulator-safety gate

- Never invoke `mgba`, `mgba-qt`, `mgba-headless`, or `xvfb-run ... mgba`
  directly.
- Headed human play must use `scripts/launch_mgba.sh`. Automated verifiers
  must use `scripts/mgba-{qt,headless}-singleflight`. Never override `--mgba`
  with an unguarded executable.
- Never run two emulator-backed commands concurrently, including through
  parallel tool calls, background jobs, subagents, or shell fan-out.
- The project-wide lock is fail-closed: exit status 75 means another emulator
  owns the slot. Wait for that exact owner to finish; do not bypass the lock.
- Never use broad `pkill`, `killall`, or pattern-based process termination.
  Stop only the exact launcher/emulator PID owned by the current command.
- After any interrupted emulator run, use the read-only
  `scripts/check_emulator_processes.sh` and report the result before starting
  another.
