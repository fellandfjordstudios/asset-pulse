#!/usr/bin/env bash
# THE CATALOG'S BAKE, THROUGH THE LIBRARY'S COOK (the library's
# fable-plans/the-bake-fills-a-store-and-counts-its-work, step F): the impostor
# atlases, then every subject cooked by the library's own `tools/cook.sh` into
# out/cooked/catalog/, against the pinned library.
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
#
# THE STORE IS THE PROGRESS. Every key is content, so a rung whose key is in the
# write store is copied, never baked again, at any pin; a run cut by its
# deadline leaves the store fuller than it found it, and the next run bakes only
# what was deferred or what moved. The workflow carries the store by a rolling
# key (store-<run>), never by the pin. There is no resume folder and no loop of
# our own: the cook's deadline, its order and its limit per item are the
# library's (plans/107 steps 7 and 9).
#
# The atlases come first, as refresh.sh ordered it: the library's
# `tools/impostor.sh` renders them into its gitignored build/artifacts/ (and its
# store), and they are copied beside the cooked rungs for the catalog. The set
# cooked is the explorer's own plan (tools/cook_manifest.gd). Nothing in the
# library's source tree is touched; `tools/sync-library.sh --verify` still holds.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LIB="$ROOT/library"
EXP="$ROOT/explorer"
LOCK="$ROOT/explorer.lock"
export GIT_TERMINAL_PROMPT=0
die() { echo "bake: $*" >&2; exit 1; }
REPO="$(sed -n 's/^repo=//p' "$LOCK")"; PIN="$(sed -n 's/^commit=//p' "$LOCK")"
[ -n "$REPO" ] && [ -n "$PIN" ] || die "explorer.lock needs repo= and commit="
[ -d "$LIB/.git" ] || die "no library/ -- run tools/sync-library.sh"
[ -x "$LIB/tools/cook.sh" ] && grep -q -- '--deadline' "$LIB/tools/cook.sh" \
  || die "the library at this pin has no tools/cook.sh --deadline (plans/107 step 9); bump the pin"
if [ ! -d "$EXP/.git" ]; then
  git clone -q "https://github.com/$REPO" "$EXP" || die "clone of $REPO failed"
fi
if [ "$(git -C "$EXP" rev-parse HEAD)" != "$PIN" ]; then
  git -C "$EXP" fetch -q origin "$PIN" 2>/dev/null || git -C "$EXP" fetch -q origin
  git -C "$EXP" checkout -q --detach "$PIN" || die "the explorer pin $PIN is not on its remote"
fi
[ -z "$(git -C "$EXP" status --porcelain)" ] || die "explorer/ has local changes; the pulse never edits it"
LOG="${BAKE_LOG:-$ROOT/out/bake.log}"
mkdir -p "$(dirname "$LOG")"
COOKED="$ROOT/out/cooked"
STORE="${AG_BAKE_CACHE:-$HOME/.cache/asset-generators/bakes}"
IMPOSTOR_ARGS=(--cache)
if [ "${PULSE_STORE:-1}" != "1" ]; then
  STORE="$ROOT/out/bake-store-this-run"; rm -rf "$STORE"; IMPOSTOR_ARGS=()
fi
mkdir -p "$STORE"
rm -rf "$LIB/build/artifacts" "$COOKED" "$ROOT/out/bake-resume"

echo "bake: impostor atlases (the library's tools/impostor.sh${IMPOSTOR_ARGS[*]:+ --cache})"
( cd "$LIB" && AG_BAKE_CACHE="$STORE" tools/impostor.sh ${IMPOSTOR_ARGS[@]+"${IMPOSTOR_ARGS[@]}"} | tail -3; exit "${PIPESTATUS[0]}" ) \
  || echo "bake: NO IMPOSTOR ATLASES this run (the library's tools/impostor.sh failed; see its log); the cook goes on and the catalog names every far rung that lacks one"

MANIFEST="$ROOT/out/cook-manifest.json"
( cd "$LIB" && godot --headless --path . --script "$ROOT/tools/cook_manifest.gd" -- "$MANIFEST" "$EXP" 2>&1 ) \
  | grep -E '^cook manifest|SCRIPT ERROR|usage' || true
[ -s "$MANIFEST" ] || die "no cook manifest (tools/cook_manifest.gd)"

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
if [ "${PULSE_TRANSFER:-0}" = "1" ]; then
  # The baked-channel bake refuses a whole cook when one rung's channel is flat
  # (core/baker.gd flat_channel_problem); the default bake, the Forward+/SDFGI
  # product, is still a correct download, so the catalog falls back to it and says so.
  if ! cook --transfer; then
    echo "bake: the baked-channel cook FAILED; falling back to the library's default bake (no baked channel)"
    cook || die "the cook failed (see $LOG)"
  fi
else
  cook || die "the cook failed (see $LOG)"
fi
OUTDIR="$COOKED/catalog"
[ -f "$OUTDIR/manifest.json" ] && [ -f "$OUTDIR/index.json" ] || die "the cook wrote no manifest"
python3 "$ROOT/tools/cook_hits.py" report "$ROOT/out/cook-store-before.txt" "$OUTDIR/index.json" | tee "$LOG.hits" | tail -1
grep -E '^bake: (made|held)' "$LOG.hits" | head -20
# THE ATLASES BESIDE THE RUNGS: the cook bakes into a folder of its own, where the
# library's impostor atlases are not (filed in the library's feedback/).
for a in "$LIB"/build/artifacts/*-impostor.png; do [ -f "$a" ] && cp "$a" "$OUTDIR/"; done
python3 "$ROOT/tools/catalog_impostors.py" --bake "$OUTDIR" || die "impostor completion failed"
"$ROOT/tools/sync-library.sh" --verify >/dev/null || die "the bake changed the library's source tree"
echo "bake: manifest at $OUTDIR/manifest.json"
