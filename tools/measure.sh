#!/usr/bin/env bash
# THE LIBRARY'S MEASUREMENTS, ON THE PULSE'S CLOCK (the library's fable-plans/the-games-are-
# repositories-and-the-core-is-tested-on-fixtures step 1, row 737).
#
#   tools/measure.sh OUT      run the library's measurement suites at the pin, into OUT
#
# The library's push gate runs its contracts on fixtures; its measurements -- instruments
# on problems nobody has solved (the derivation's searches and tables, coverage, ...) --
# left that gate for this schedule. They are the library's own suites, named by its
# ops/suite-kinds.json and run by its own runner (`tools/test.sh --kind measurement`);
# this script decides nothing about them. A suite refuses only a regression below its
# recorded floor (its assertions, its ledger); a red one is a line in the day's report,
# never a silent skip, and never stops the run.
#
# Writes OUT/measurements.log (the runner's log) and OUT/measurements.txt (one line:
# `measurements: green|RED|skipped ...`), which daily.sh prints.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:?tools/measure.sh OUT}"
mkdir -p "$OUT"
LINE="$OUT/measurements.txt"
if ! grep -q -- '--kind)' "$ROOT/library/tools/test.sh" 2>/dev/null; then
  echo "measurements: skipped -- the library at this pin has no tools/test.sh --kind" > "$LINE"
  exit 0
fi
SECONDS=0
( cd "$ROOT/library" && AG_RUNNER=1 LOG="$OUT/measurements.log" tools/test.sh --kind measurement ) \
  > "$OUT/measurements.out" 2>&1
code=$?
ran="$(grep -cE '^  \S+\s+[0-9]+\.[0-9]+s\s' "$OUT/measurements.log" 2>/dev/null || echo 0)"
if [ "$code" = 0 ]; then
  echo "measurements: green, ${ran} suite(s) in ${SECONDS}s (the library's tools/test.sh --kind measurement)" > "$LINE"
else
  red="$(grep -E '^  failed in: |^  (FAIL|BUDGET|SILENT) ' "$OUT/measurements.log" 2>/dev/null | head -5 | tr '\n' ' ')"
  echo "measurements: RED (exit $code), ${ran} suite(s) in ${SECONDS}s -- a regression below a recorded floor: ${red:-see $OUT/measurements.log}" > "$LINE"
fi
cat "$LINE"
exit 0
