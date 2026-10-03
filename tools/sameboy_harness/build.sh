#!/usr/bin/env bash
# Build libsbh.so: SameBoy's core plus sbh.c (VRAM / CGB palette / OAM write
# logger using the core's own access-blocked flags). Needs git, cc, curl, xz.
# Usage: tools/sameboy_harness/build.sh [workdir]   (default /tmp/sbh-build)
set -euo pipefail
W=${1:-/tmp/sbh-build}; H=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$W" && cd "$W"
[ -d SameBoy ] || git clone -q --depth 1 https://github.com/LIJI32/SameBoy.git
if ! command -v rgbasm >/dev/null; then
  T=$(curl -sI https://github.com/gbdev/rgbds/releases/latest | grep -i ^location | sed 's#.*/tag/##;s/\r//')
  mkdir -p rgbds && curl -sfL https://github.com/gbdev/rgbds/releases/download/$T/rgbds-linux-x86_64.tar.xz | tar -xJ -C rgbds
  export PATH=$W/rgbds:$PATH
fi
cd SameBoy && make -s tester CONF=release           # boot ROMs (cgb_boot.bin)
mkdir -p "$W/o"
for f in Core/*.c; do
  case $f in *cheat_search.c) continue;; esac
  cc -O2 -fPIC -std=gnu11 -D_GNU_SOURCE -DGB_VERSION='"sbh"' -DGB_COPYRIGHT_YEAR='"2026"' -I. -DGB_INTERNAL \
     -DGB_DISABLE_CHEAT_SEARCH -w -c "$f" -o "$W/o/$(basename "$f").o"
done
cc -O2 -fPIC -std=gnu11 -D_GNU_SOURCE -DGB_DISABLE_CHEAT_SEARCH -ICore -I. -c "$H/sbh.c" -o "$W/o/sbh.o"
cc -shared -o "$W/libsbh.so" "$W"/o/*.o -lm
cp build/bin/tester/cgb_boot.bin "$W/"
echo "$W/libsbh.so"
