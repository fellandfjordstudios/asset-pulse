#!/bin/bash
# THE DERIVATION BACKLOG, PAID ONCE (the owner, 2026-10-02: "let asset pulse fix
# the derivation ... I don't want to pay twice for a super expensive job").
#
# The library's expensive searches -- the derivation benchmark, the goal table,
# every derived record and drawn ladder another deriver wrote -- run here, once
# a day, by the library's own job (`tools/derive-backlog.sh` in the library).
# The pulse's sheets then READ what it found (the library's rung-sheet takes the
# goal table's entries) instead of searching again.
#
# What the job writes is the library's, so it goes back to the library: only
# the files the job writes are committed, on top of the library's main, and
# pushed through the library's own gate. If the gate refuses or main moved under
# them, they go to `run/derive-backlog-<date>` (exempt from the gate) for the
# library's derivation seat to merge -- never lost, never paid for twice. This is
# the one place the pulse writes to the library.
#
#   tools/backlog.sh          run it, commit and push
#   tools/backlog.sh --list   what is on the backlog, nothing run
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LIB="$ROOT/library"
DATE="$(date -u +%Y-%m-%d)"
[ -d "$LIB/.git" ] || { echo "backlog: no library/ -- run tools/sync-library.sh"; exit 1; }
if [ "${1:-}" = "--list" ]; then
  ( cd "$LIB" && tools/derive-backlog.sh --list )
  exit $?
fi
( cd "$LIB" && tools/derive-backlog.sh ) || { echo "backlog: the library's job failed"; exit 1; }
cd "$LIB"
# ONLY WHAT THE JOB WRITES: the two tables and the records beside generators
# and fixtures. Anything else changed in library/ is not the pulse's.
git add -A test/derive_bench.json test/derive_goal.json test/derive_bench.build_ms.json test/derive_goal.build_ms.json 2>/dev/null
git add -A -- 'generators/*.derived.json' 'generators/*.drawn.json' 'test/fixtures/*.derived.json' 2>/dev/null
if git diff --cached --quiet; then
  echo "backlog: nothing to commit -- the backlog was clear"
  exit 0
fi
git -c user.name="asset-pulse" -c user.email="asset-pulse@users.noreply.github.com" commit -q \
  -m "derivation backlog cleared by asset-pulse, $DATE" \
  -m "tools/derive-backlog.sh: the benchmark, the goal table, the stale derived records and drawn ladders, run once by the daily job (the owner, 2026-10-02)." \
  || { echo "backlog: commit failed"; exit 1; }
BRANCH="run/derive-backlog-$DATE"
git fetch -q origin main
if git merge -q --no-edit origin/main && git push -q origin HEAD:main; then
  NEW="$(git rev-parse HEAD)"
  echo "backlog: pushed to the library's main at $NEW"
  cd "$ROOT" && tools/sync-library.sh --bump "$NEW" >/dev/null && echo "backlog: pin moved to $NEW"
  exit 0
fi
git merge --abort 2>/dev/null
git push -q -f origin HEAD:"$BRANCH" && echo "backlog: main refused or moved -- the records are on $BRANCH for the library to merge"
exit 0
