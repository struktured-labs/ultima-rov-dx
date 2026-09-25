# Release packaging (placeholder)

Mirrors penta-dragon-dx's release rules, to be filled in as the project matures:

1. Build twice from a clean tree; outputs must be byte-identical.
2. Run the full emulator verification matrix serially (single-flight guard).
3. Bind the result to source + ROM hash in a ROM-free receipt under
   `docs/release/verification/`.
4. Ship only `rom/ultima_rov_dx.ips` (plus screenshots/readme). State the
   required source MD5 (`411c3d168141d10eddd93243f2a7765f`) and the resulting
   SHA-256 of the patched ROM.
5. Every intentional difference from the original must be listed in
   `known_deviations.md`; anything else is a defect.
