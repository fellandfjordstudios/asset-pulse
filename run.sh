#!/bin/bash
# THE PULSE, ONE RUN: sync the library to its pin, print the scorecard, append
# the day's totals to history.csv, render every subject's bands (step 1, with
# the library's per-band sheet, step 5) and write the page (step 2, out/<date>/site/).
#
#   ./run.sh                 one run, into out/<date>/
#   ./run.sh --bump          first move the pin to the library's main
#   ./run.sh --no-render     the scorecard and the row only
#   PULSE_CAP_S=1800         the per-subject time cap for the renders
#   PULSE_BACKLOG=0          skip the derivation backlog (tools/backlog.sh, on by default)
#   PULSE_DERIVE=none        drawn today only: no derived column
#   PULSE_ONLY="a/b c/d"     render only these subjects (a manual look)
#   PULSE_BAKE=0             skip the bake and the catalog (tools/bake.sh, tools/catalog.py)
#   PULSE_TRANSFER=0         bake without the baked channel (fast, structural only)
#   PULSE_RESUME=1           resume an interrupted run: a subject whose sheet and
#                            close-up are already in out/<date>/ from the SAME
#                            library pin is not rendered again (a container
#                            restart or a time limit costs minutes, not hours);
#                            off by default, so a daily run always renders fresh
#
# Rules (fable-plans/active/the-pulse-is-a-consumer, in the library):
#   - every number comes from the library's scorecard tool, every frame from the
#     library's sheet and close-up tools; this script decides nothing about
#     scoring or rendering;
#   - nothing generated is committed here but history.csv, one dated row per run;
#     the derivation backlog's records go to the library (tools/backlog.sh);
#   - a failed run writes a row that says so, never nothing.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
DATE="$(date -u +%Y-%m-%d)"
OUT="$ROOT/out/$DATE"
mkdir -p "$OUT"
HIST="$ROOT/history.csv"
[ -f "$HIST" ] || echo "date,pin,status,subjects,bands,covered_hand,covered_library,uncovered,fully_covered,fully_from_rung0,sources_over_ceiling" > "$HIST"
fail_row() {
  PIN="$(sed -n 's/^commit=//p' library.lock)"
  echo "$DATE,$PIN,failed:$1,,,,,,,," >> "$HIST"
  echo "run: FAILED ($1); a row says so in history.csv" >&2
  exit 1
}
if [ "${1:-}" = "--bump" ]; then
  tools/sync-library.sh --bump main || fail_row "bump"
fi
tools/sync-library.sh || fail_row "sync"
tools/sync-library.sh --verify || fail_row "verify"
# THE DERIVATION BACKLOG, PAID ONCE, before the sheets read it (tools/backlog.sh):
# the library's own job, its records pushed back to the library. PULSE_BACKLOG=0
# skips it (a quick manual look).
if [ "${PULSE_BACKLOG:-1}" = "1" ] && [ "${1:-}" != "--no-render" ] && [ "${2:-}" != "--no-render" ]; then
  tools/backlog.sh || echo "run: the backlog failed; the sheets read the tables as they are"
fi
PIN="$(sed -n 's/^commit=//p' library.lock)"
# THE SCORECARD: the library's tool when it exists (the tooling plan's step 10),
# the prototype beside the library's plans until then. Run from the library root,
# since both read the library's committed JSON by relative path.
SCORECARD="library/tools/scorecard.py"
[ -f "$SCORECARD" ] || SCORECARD="library/fable-plans/notes/scorecard-prototype.py"
( cd library && python3 "../$SCORECARD" ) > "$OUT/scorecard.txt" || fail_row "scorecard"
TOTALS="$( cd library && python3 "../$SCORECARD" --json )" || fail_row "scorecard-json"
ROW="$(python3 - "$DATE" "$PIN" "$TOTALS" <<'PY'
import json, sys
d, pin, raw = sys.argv[1], sys.argv[2], json.loads(sys.argv[3])
# tools/scorecard.py (the library's, since 2026-10-03) nests its totals beside
# the per-subject rows; the prototype printed them flat. The names are its own.
t = raw.get("totals", raw)
pick = lambda *ks: next(t[k] for k in ks if k in t)
print(",".join(str(x) for x in [d, pin, "ok", pick("subjects"), pick("bands"), pick("covered_hand"),
      pick("covered_library", "covered_derived"), pick("uncovered"), pick("fully"),
      pick("fully_from_rung0", "fully_rung0_only"), pick("src_over")]))
PY
)" || fail_row "row"
# One row per date: a re-run on the same day replaces the day's row.
grep -v "^$DATE," "$HIST" > "$HIST.tmp" && mv "$HIST.tmp" "$HIST"
echo "$ROW" >> "$HIST"
echo "run: scorecard in $OUT/scorecard.txt; history row: $ROW"
# STEP 1, THE RENDERS: the library's own sheet and close-up for every subject
# that has a card, each under a per-subject time cap, into out/<date>/<id>/.
# The library decides every frame (tools/rung-sheet.py, tools/closeup.sh); this
# loop only names the subject and the directory. A subject that fails gets a
# manifest row that says so, and the run goes on. `--no-render` skips it.
if [ "${PULSE_RENDER:-1}" = "1" ] && [ "${1:-}" != "--no-render" ] && [ "${2:-}" != "--no-render" ]; then
  command -v godot >/dev/null 2>&1 || fail_row "godot-missing"
  command -v xvfb-run >/dev/null 2>&1 || fail_row "xvfb-missing"
  # A fresh checkout has no class cache; the import builds it (seconds) and is
  # a no-op when it exists for this pin.
  if [ ! -f library/.godot/global_script_class_cache.cfg ] || [ "$(cat library/.godot/pulse-pin 2>/dev/null)" != "$PIN" ]; then
    ( cd library && godot --headless --path . --import >/dev/null 2>&1 ) || fail_row "import"
    echo "$PIN" > library/.godot/pulse-pin
  fi
  CAP="${PULSE_CAP_S:-1800}"
  # THE PER-BAND SHEET (the plan's step 5, the library's plans/049 step 3): each
  # band drawn today beside the rung derived from rung 0, and its numbers as
  # sheet-bands.json for the page. The derived column READS the goal table the
  # backlog step just wrote -- no search here; PULSE_DERIVE=none leaves it out.
  SHEET_ARGS=()
  [ "${PULSE_DERIVE:-}" = "none" ] && SHEET_ARGS=(--derive none)
  MANIFEST="$OUT/manifest.json"
  # RESUME only renders this pin made: out/<date>/render-pin records it, and a
  # pin moved since (a --bump the same day) renders everything again.
  RESUME=0
  if [ "${PULSE_RESUME:-0}" = "1" ] && [ "$(cat "$OUT/render-pin" 2>/dev/null)" = "$PIN" ]; then RESUME=1; fi
  echo "$PIN" > "$OUT/render-pin"
  echo "[" > "$MANIFEST"; first=1; n=0; failed=0; resumed=0; t0=$(date +%s)
  for card in library/generators/*/*.card.json; do
    id="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['id'])" "$card" 2>/dev/null)" || continue
    [ -n "$id" ] || continue
    if [ -n "${PULSE_ONLY:-}" ] && [[ " $PULSE_ONLY " != *" $id "* ]]; then continue; fi
    dir="$OUT/${id//\//_}"; mkdir -p "$dir"
    s=$(date +%s); status="ok"
    # A subject done at this pin is not done again: its status file says how it
    # ended (a failure at the same pin fails the same way; row 215), and a
    # directory from before the status file counts as done when its images are.
    prev=""
    if [ "$RESUME" = 1 ]; then
      prev="$(cat "$dir/status" 2>/dev/null)"
      if [ -z "$prev" ] && ls "$dir"/sheet*.jpg >/dev/null 2>&1 && ls "$dir"/*closeup*.png >/dev/null 2>&1; then prev="ok"; fi
    fi
    if [ -n "$prev" ]; then
      n=$((n+1)); resumed=$((resumed+1)); [ "$prev" = "ok" ] || failed=$((failed+1))
      images="$(cd "$dir" && ls *.jpg *.png 2>/dev/null | python3 -c "import json,sys; print(json.dumps(sys.stdin.read().split()))")"
      [ $first = 1 ] || echo "," >> "$MANIFEST"; first=0
      printf '  {"id": "%s", "status": "%s", "seconds": 0, "images": %s}' "$id" "$prev" "$images" >> "$MANIFEST"
      echo "render $id: $prev (resumed: already done at this pin)"; continue
    fi
    ( cd library && timeout "$CAP" python3 tools/rung-sheet.py "$id" --out "$dir/sheet.jpg" "${SHEET_ARGS[@]}" ) > "$dir/sheet.log" 2>&1 || status="sheet-failed"
    if [ "$status" = "ok" ]; then
      ( cd library && SHOT_DIR="$dir" timeout "$CAP" tools/closeup.sh "$id" ) > "$dir/closeup.log" 2>&1 || status="closeup-failed"
    fi
    secs=$(( $(date +%s) - s )); n=$((n+1)); [ "$status" = "ok" ] || failed=$((failed+1))
    echo "$status" > "$dir/status"
    images="$(cd "$dir" && ls *.jpg *.png 2>/dev/null | python3 -c "import json,sys; print(json.dumps(sys.stdin.read().split()))")"
    [ $first = 1 ] || echo "," >> "$MANIFEST"; first=0
    printf '  {"id": "%s", "status": "%s", "seconds": %d, "images": %s}' "$id" "$status" "$secs" "$images" >> "$MANIFEST"
    echo "render $id: $status in ${secs}s"
  done
  echo "" >> "$MANIFEST"; echo "]" >> "$MANIFEST"
  echo "run: rendered $n subjects ($resumed resumed), $failed failed, in $(( $(date +%s) - t0 )) s; manifest $MANIFEST"
  # STEP 2, THE PAGE: static HTML from this run's output and the history.
  python3 tools/site.py "$OUT" || fail_row "site"
  # THE CATALOG, the pulse's public half: the explorer's bake of every rung
  # (tools/bake.sh), then the cards, the 3D view and the free downloads. A
  # failed bake leaves the private page and the row standing and says so.
  if [ "${PULSE_BAKE:-1}" = "1" ]; then
    if BAKE_LOG="$OUT/bake.log" tools/bake.sh; then
      python3 tools/catalog.py "$OUT" || echo "run: the catalog failed; the pulse's page stands"
    else
      echo "run: the bake failed (see $OUT/bake.log); no catalog this run"
    fi
  fi
else
  echo "run: renders skipped (--no-render)"
fi
