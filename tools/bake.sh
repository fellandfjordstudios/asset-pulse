#!/usr/bin/env bash
# THE CATALOG'S BAKE, THROUGH THE LIBRARY'S COOK (the library's
# fable-plans/the-bake-fills-a-store-and-counts-its-work, step F): the impostor
# atlases, then every subject cooked by the library's own `tools/cook.sh` into
# out/cooked/catalog/, against the pinned library. The set is the library's own
# plan (`tools/bake-library.gd`, moved there from asset-explorer by its row
# 324); the explorer is no part of the bake (row 712).
#
#   tools/bake.sh                    impostor atlases, then the cook (structural)
#   PULSE_TRANSFER=1 tools/bake.sh   cook with the baked channel (--transfer)
#   PULSE_BAKE_BUDGET_S=2700         the cook's deadline, that many seconds from its
#                                    start (--deadline): only items that fit what
#                                    remains are begun, the rest deferred by name;
#                                    unset, no deadline
#   PULSE_BAKE_ITEM_LIMIT=3          an item past that many times its recorded cost
#                                    is stopped (--item-limit), put back once, and
#                                    failed by name on a second overrun
#   PULSE_BAKE_SUBJECT_CAP_S=600     the limit's floor (--item-floor), for an item
#                                    never seen or a cheap one
#   PULSE_BAKE_ORDER=fits+shuffle:<n>  the cook's order (--order); by default the
#                                    fit test, then an order seeded by the run's
#                                    number, so a budget is spread across runs
#   PULSE_STORE=0                    a store of this run's own: everything is baked
#   PULSE_BAKE_ONLY="stone/pebble built/matchbox"
#                                    only these generators' subjects, atlases and
#                                    cook (the store gate, tools/test_bake_pins.sh)
#
# THE STORE IS THE PROGRESS. Every key is content, so a rung whose key is in the
# write store is copied, never baked again, at any pin; a run cut by its
# deadline leaves the store fuller than it found it, and the next run bakes only
# what was deferred or what moved. The workflow carries the store by a rolling
# key (store-<run>), never by the pin. There is no resume folder and no loop of
# our own: the cook's deadline, its order and its limit per item are the
# library's (plans/107 steps 7 and 9).
#
# A COOK THAT FAILS WHOLE IS NOT "NO CATALOG" (row 712; the bake plan's step
# E). Exit 2 says the cook ran and assembled nothing: run.sh then builds the
# catalog with CATALOG_NO_BAKE, every subject from its last good build, and the
# guard decides as on any run. One item that kills its worker costs only that
# item once the pinned library carries row 712's cook (it is failed by name in
# the index, and `bake: held` names it here); exit 2 is for what is left.
#
# The atlases come first, as refresh.sh ordered it: the library's
# `tools/impostor.sh` renders them into its gitignored build/artifacts/ (and its
# store), and they are copied beside the cooked rungs for the catalog (the cook
# writes no atlas yet: the library's feedback/no-impostor-atlas-can-be-baked).
# The set cooked is the library's plan (tools/cook_manifest.gd). Nothing in the
# library's source tree is touched; `tools/sync-library.sh --verify` still holds.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LIB="$ROOT/library"
die() { echo "bake: $*" >&2; exit 1; }
[ -d "$LIB/.git" ] || die "no library/ -- run tools/sync-library.sh"
[ -x "$LIB/tools/cook.sh" ] && grep -q -- '--deadline' "$LIB/tools/cook.sh" \
  || die "the library at this pin has no tools/cook.sh --deadline (plans/107 step 9); bump the pin"
[ -f "$LIB/tools/bake-library.gd" ] || die "the library at this pin has no tools/bake-library.gd (its row 324); bump the pin"
LOG="${BAKE_LOG:-$ROOT/out/bake.log}"
mkdir -p "$(dirname "$LOG")" "$ROOT/out"
COOKED="$ROOT/out/cooked"
STORE="${AG_BAKE_CACHE:-$HOME/.cache/asset-generators/bakes}"
IMPOSTOR_ARGS=(--cache)
if [ "${PULSE_STORE:-1}" != "1" ]; then
  STORE="$ROOT/out/bake-store-this-run"; rm -rf "$STORE"; IMPOSTOR_ARGS=()
fi
mkdir -p "$STORE"
rm -rf "$LIB/build/artifacts" "$COOKED" "$ROOT/out/bake-resume"

echo "bake: impostor atlases (the library's tools/impostor.sh${IMPOSTOR_ARGS[*]:+ --cache})"
read -r -a ONLY <<< "${PULSE_BAKE_ONLY:-}"
( cd "$LIB" && AG_BAKE_CACHE="$STORE" tools/impostor.sh ${IMPOSTOR_ARGS[@]+"${IMPOSTOR_ARGS[@]}"} ${ONLY[@]+"${ONLY[@]}"} | tail -3; exit "${PIPESTATUS[0]}" ) \
  || echo "bake: NO IMPOSTOR ATLASES this run (the library's tools/impostor.sh failed; see its log); the cook goes on and the catalog names every far rung that lacks one"

MANIFEST="$ROOT/out/cook-manifest.json"
( cd "$LIB" && godot --headless --path . --script "$ROOT/tools/cook_manifest.gd" -- "$MANIFEST" 2>&1 ) \
  | grep -E '^cook manifest|SCRIPT ERROR|usage' || true
[ -s "$MANIFEST" ] || die "no cook manifest (tools/cook_manifest.gd)"
if [ "${#ONLY[@]}" -gt 0 ]; then
  python3 - "$MANIFEST" "${ONLY[@]}" <<'PY'
import json, sys
m = json.load(open(sys.argv[1])); keep = set(sys.argv[2:])
m["subjects"] = [s for s in m["subjects"] if s["generator"] in keep]
json.dump(m, open(sys.argv[1], "w"), indent=2)
print("bake: PULSE_BAKE_ONLY: %d subject(s) of %s" % (len(m["subjects"]), " ".join(sorted(keep))))
PY
fi

ARGS=(--target=catalog --out "$COOKED" --write "$STORE"
  "--item-limit=${PULSE_BAKE_ITEM_LIMIT:-3}" "--item-floor=${PULSE_BAKE_SUBJECT_CAP_S:-600}")
[ -n "${PULSE_BAKE_ORDER:-}" ] && ARGS+=("--order=$PULSE_BAKE_ORDER")
if [ -n "${PULSE_BAKE_BUDGET_S:-}" ]; then
  ARGS+=("--deadline=$(( $(date +%s) + PULSE_BAKE_BUDGET_S ))")
  [ -n "${PULSE_BAKE_ORDER:-}" ] || ARGS+=("--order=fits+shuffle:${GITHUB_RUN_NUMBER:-$(date -u +%Y%m%d)}")
fi
python3 "$ROOT/tools/cook_hits.py" before "$STORE" "$ROOT/out/cook-store-before.txt"
cook() { # [--transfer]
  echo "bake: the library's tools/cook.sh ${ARGS[*]} $*"
  ( cd "$LIB" && tools/cook.sh "$MANIFEST" "${ARGS[@]}" "$@" ) > "$LOG" 2>&1
  local code=$?
  # The cook's own report, without its line a layer a rung (out/bake.log keeps those).
  grep -v -E '^  [^ ]+-r[0-9]+ +(mesh|bake|cook|channel|measure) +\((cached|made)' "$LOG" | sed 's/^/  /'
  # A failed worker's own log stays on the runner; its tail names the item.
  if [ "$code" != 0 ]; then
    for w in "$LIB"/.git/ag-logs/cook.log.work*; do
      [ -f "$w" ] || continue
      echo "bake: the tail of $(basename "$w"):"; tail -n 25 "$w" | sed 's/^/    /'
    done
  fi
  return "$code"
}
no_bake() { # <why>: the cook assembled nothing; run.sh serves every last good build
  echo "bake: NO BAKE this run: $1 (see $LOG); the catalog serves each subject's last good build"
  "$ROOT/tools/sync-library.sh" --verify >/dev/null || die "the bake changed the library's source tree"
  exit 2
}
if [ "${PULSE_TRANSFER:-0}" = "1" ]; then
  # The baked-channel bake refuses a whole cook when one rung's channel is flat
  # (core/baker.gd flat_channel_problem); the default bake, the Forward+/SDFGI
  # product, is still a correct download, so the catalog falls back to it and says so.
  if ! cook --transfer; then
    echo "bake: the baked-channel cook FAILED; falling back to the library's default bake (no baked channel)"
    cook || no_bake "the cook failed"
  fi
else
  cook || no_bake "the cook failed"
fi
OUTDIR="$COOKED/catalog"
[ -f "$OUTDIR/manifest.json" ] && [ -f "$OUTDIR/index.json" ] || no_bake "the cook wrote no manifest"
python3 "$ROOT/tools/cook_hits.py" report "$ROOT/out/cook-store-before.txt" "$OUTDIR/index.json" | tee "$LOG.hits" | tail -1
grep -E '^bake: made' "$LOG.hits" | head -20
# EVERY SUBJECT THE COOK HELD BACK, by name (the bake plan's step E): failed
# (one that killed its worker twice, or ran past its limit twice) or deferred.
grep -E '^bake: held' "$LOG.hits"
# THE ATLASES BESIDE THE RUNGS: the cook bakes into a folder of its own, where the
# library's impostor atlases are not (filed in the library's feedback/).
for a in "$LIB"/build/artifacts/*-impostor.png; do [ -f "$a" ] && cp "$a" "$OUTDIR/"; done
python3 "$ROOT/tools/catalog_impostors.py" --bake "$OUTDIR" || die "impostor completion failed"
"$ROOT/tools/sync-library.sh" --verify >/dev/null || die "the bake changed the library's source tree"
echo "bake: manifest at $OUTDIR/manifest.json"
