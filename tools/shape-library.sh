#!/usr/bin/env bash
# THE SHAPE LIBRARY BEFORE THE RENDERS AND THE BAKE (row 839). The sculpt kit's
# body (the library's AgShapeLibrary, core/sculpt/shape_library.gd) reads
# MakeHuman's CC0 base and targets from library/plates/incoming/shape-library/;
# without them every subject built on that body (specimen/arms, animal/human,
# built/fisherman-trousers, built/fisherman-wool-jumper) builds nothing, and the
# catalog showed them with no model. The library's setup fetches it only from
# the private references bucket, with credentials the pulse does not hold.
#
#   tools/shape-library.sh           provide it: the library's own
#                                    `tools/shape-library.sh bake` (MakeHuman's
#                                    public add-on zip, held to its sha256 by the
#                                    library), the pack held here to
#                                    AgShapeLibrary.SOURCE's pack_sha256, then
#                                    unpacked as the library's `fetch` unpacks it
#   PULSE_SHAPE_LIBRARY=0            do not provide it (the ablation): one already
#                                    in place is used, else it is said absent, the
#                                    four subjects' gaps come back and the catalog
#                                    names why
#
# No credential and no copy: the pack is made by the library's tool from a
# public CC0 download, and refused unless it hashes to the library's own pin.
# Nothing lands in the library's source tree: plates/incoming/ is gitignored
# there, a .gdignore keeps Godot from importing it, and
# `tools/sync-library.sh --verify` still holds. A pack already in place at the
# pinned hash is kept (the marker .pulse-pack names it).
#
# Exit: 0 held, 1 refused or absent.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LIB="$ROOT/library"
DIR="$LIB/plates/incoming/shape-library"
say() { echo "shape-library: $*"; }
refuse() { say "ABSENT: $*; the subjects built on the sculpt kit's body will build nothing"; exit 1; }
[ -d "$LIB/.git" ] || refuse "no library/ -- run tools/sync-library.sh"
[ -f "$LIB/tools/shape-library.sh" ] && grep -q '^bake)' "$LIB/tools/shape-library.sh" \
  || refuse "the library at this pin has no tools/shape-library.sh bake"
WANT="$(sed -n 's/.*"pack_sha256": *"\([0-9a-f]\{64\}\)".*/\1/p' "$LIB/core/sculpt/shape_library.gd" | head -1)"
[ -n "$WANT" ] || refuse "no pack_sha256 in the library's AgShapeLibrary.SOURCE"
held() {
  [ -f "$DIR/3dobjs/base.obj" ] && [ -d "$DIR/targets" ] && [ -f "$DIR/rigs/standard/weights.game_engine.json" ]
}
if held && [ "$(cat "$DIR/.pulse-pack" 2>/dev/null)" = "$WANT" ]; then
  say "HELD pack $WANT (already in place)"; exit 0
fi
if [ "${PULSE_SHAPE_LIBRARY:-1}" != "1" ]; then
  held && { say "HELD (not provided: PULSE_SHAPE_LIBRARY=${PULSE_SHAPE_LIBRARY}; one is already in place)"; exit 0; }
  refuse "not provided (PULSE_SHAPE_LIBRARY=${PULSE_SHAPE_LIBRARY})"
fi
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
( cd "$LIB" && bash tools/shape-library.sh bake "$tmp/pack.zip" ) | sed 's/^/  /'
[ -s "$tmp/pack.zip" ] || refuse "the library's tools/shape-library.sh bake made no pack"
GOT="$(sha256sum "$tmp/pack.zip" | cut -d' ' -f1)"
[ "$GOT" = "$WANT" ] || refuse "the baked pack has sha256 $GOT, not AgShapeLibrary.SOURCE's $WANT; nothing kept"
mkdir "$tmp/lib" && ( cd "$tmp/lib" && unzip -q ../pack.zip ) || refuse "the pack does not unzip"
DIR_NEW="$tmp/lib"
[ -f "$DIR_NEW/3dobjs/base.obj" ] && [ -d "$DIR_NEW/targets" ] && [ -f "$DIR_NEW/rigs/standard/weights.game_engine.json" ] \
  || refuse "the pack has no 3dobjs/base.obj, targets/ or the game_engine weights"
rm -rf "$DIR"
mkdir -p "$(dirname "$DIR")"
mv "$DIR_NEW" "$DIR"
: > "$DIR/.gdignore"
echo "$WANT" > "$DIR/.pulse-pack"
say "HELD pack $WANT, baked from MakeHuman's CC0 zip ($(find "$DIR/targets" -name '*.target*' | wc -l) targets)"
