#!/usr/bin/env bash
# THE SUBJECTS ON THE SCULPT KIT'S BODY BAKE ONLY WITH THE SHAPE LIBRARY (row 839).
# Two bakes of those subjects through tools/bake.sh, each in a scratch copy of
# this repository (tools/, library.lock, library/ cloned at the pin, with no
# shape library in it), into stores of their own:
#
#   with:     tools/shape-library.sh provides it; every subject must cook rung 0
#             and the bake's record must say HELD
#   ablation: PULSE_SHAPE_LIBRARY=0; no subject may cook, the record must say
#             absent, and tools/catalog.py's gap line must name the shape library
#             on each of them (not "not ready yet")
#
#   tools/test_shape_library.sh [<generator>...]
#        default: specimen/arms built/fisherman-trousers
#                 built/fisherman-wool-jumper animal/human
#   KEEP=1   keep the scratch directory
# Expensive (two cooks); never part of tools/check.sh.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GENS="${*:-specimen/arms built/fisherman-trousers built/fisherman-wool-jumper animal/human}"
export PATH="$HOME/.local/bin:$PATH"
[ -d "$ROOT/library/.git" ] || { echo "test_shape_library: no library/ -- run tools/sync-library.sh"; exit 1; }
T="$(mktemp -d "${TMPDIR:-/tmp}/pulse-shape-library.XXXXXX")"
[ -n "${KEEP:-}" ] && echo "test_shape_library: kept in $T" || trap 'rm -rf "$T"' EXIT
PIN="$(sed -n 's/^commit=//p' "$ROOT/library.lock")"
fail=0
bad() { echo "FAIL: $*"; fail=1; }
bake() { # <name> [env...]
  local name="$1"; shift
  local W="$T/$name"
  mkdir -p "$W/out"
  cp -r "$ROOT/tools" "$W/tools"; cp "$ROOT/library.lock" "$ROOT/catalog.json" "$W/"
  git clone -q --shared "$ROOT/library" "$W/library" && git -C "$W/library" checkout -q --detach "$PIN" || return 1
  [ ! -e "$W/library/plates/incoming/shape-library" ] || { echo "the scratch library already has a shape library"; return 1; }
  ( cd "$W/library" && godot --headless --path . --import >/dev/null 2>&1 )
  env "$@" AG_BAKE_CACHE="$W/store" PULSE_BAKE_ONLY="$GENS" BAKE_LOG="$W/bake.log" "$W/tools/bake.sh" > "$W/out.txt" 2>&1
  echo "bake $name: exit $? -- $(cat "$W/out/cooked/shape-library.txt" 2>/dev/null)"
}
cooked() { # <name> <generator>: the number of rungs the cook's index ships for it
  python3 - "$T/$1/out/cooked/catalog/index.json" "$2" <<'PY'
import json, sys
try:
    idx = json.load(open(sys.argv[1]))
except Exception:
    print(0); sys.exit()
stem = sys.argv[2].replace("/", "-")
print(sum(1 for r in idx.get("rungs", []) if r.get("stem", "") == stem or r.get("stem", "").startswith(stem + "-")))
PY
}
bake with || bad "the bake with the shape library did not run"
grep -q "HELD" "$T/with/out/cooked/shape-library.txt" 2>/dev/null || bad "with: the bake's record does not say HELD"
for g in $GENS; do
  n="$(cooked with "$g")"; echo "  with:     $g: $n rung(s)"
  [ "$n" -gt 0 ] || bad "with: $g cooked nothing"
done
bake ablation PULSE_SHAPE_LIBRARY=0 || bad "the ablation bake did not run"
grep -q "^absent" "$T/ablation/out/cooked/shape-library.txt" 2>/dev/null || bad "ablation: the bake's record does not say absent"
for g in $GENS; do
  n="$(cooked ablation "$g")"; echo "  ablation: $g: $n rung(s)"
  [ "$n" -eq 0 ] || bad "ablation: $g cooked without the shape library"
done
# The ablation's catalog: the gap line names the shape library on each subject.
mkdir -p "$T/ablation/out/fixture"
( cd "$T/ablation" && CATALOG_NO_BAKE="test" python3 tools/catalog.py out/fixture > catalog.out 2>&1 ) \
  || { tail -5 "$T/ablation/catalog.out"; bad "ablation: tools/catalog.py failed"; }
for g in $GENS; do
  page="$T/ablation/out/fixture/catalog/subject/$g/index.html"
  if [ ! -f "$page" ]; then bad "ablation: no catalog page for $g"; continue; fi
  grep -q "the shape library was absent from this bake" "$page" || bad "ablation: $g's gap does not name the shape library"
done
[ "$fail" = 0 ] && echo "test_shape_library: HELD -- with it every subject cooks; without it none does and the catalog says why"
exit "$fail"
