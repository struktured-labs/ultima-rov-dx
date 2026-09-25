# Launch Game

Launch the Ultima: Runes of Virtue DX ROM in mGBA through the project's
single-flight guardian.

## Steps

1. Build first if needed: `uv run python scripts/build_dx.py`.
2. Optional preflight: `uv run python scripts/launch_gate.py rom/working/ultima_rov_dx.gb`.
3. Launch (from the repo root; no pipes or redirects):
   ```bash
   scripts/launch_mgba.sh rom/working/ultima_rov_dx.gb
   ```
   Keep the command session alive while the window is open; the launcher is
   the emulator's parent-death guardian. On NVIDIA hosts set `ROV_MGBA_NVIDIA=1`.
4. Check status with the read-only script: `scripts/check_emulator_processes.sh`.

## Critical Notes
- NEVER invoke raw `mgba-qt`, use `pkill`/`killall`, or launch a second
  emulator. The project lock rejects concurrent instances with status 75.
