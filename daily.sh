#!/bin/bash
# THE PULSE'S DAILY RUN, ONE COMMAND: everything a scheduled session does.
#
#   ./daily.sh        bump the pin, run (backlog, scorecard, sheets, page),
#                     commit history.csv and the pin, push, print the report
#
# The report's last block is what a session relays. A failed step still ends
# in a report and a committed history row that says so (run.sh's rule).
set -uo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
DATE="$(date -u +%Y-%m-%d)"
OUT="out/$DATE"
mkdir -p "$OUT"
LOG="$OUT/daily.log"
SECONDS=0
[ -x .claude/hooks/session-start.sh ] && command -v godot >/dev/null 2>&1 || bash .claude/hooks/session-start.sh >>"$LOG" 2>&1
git pull -q --rebase --autostash origin main >>"$LOG" 2>&1
{ tools/sync-library.sh --bump main && ./run.sh; } >>"$LOG" 2>&1
RUN=$?
git add history.csv library.lock
if ! git diff --cached --quiet; then
  git -c user.name="asset-pulse" -c user.email="asset-pulse@users.noreply.github.com" commit -q -m "pulse $DATE" >>"$LOG" 2>&1
  for i in 1 2 3; do git pull -q --rebase --autostash origin main >>"$LOG" 2>&1 && git push -q origin HEAD:main >>"$LOG" 2>&1 && break; sleep 5; done
fi
# PUBLISH (the plan's step 3): the pulse behind Access, the catalog on the
# explorer's hostname, the objects to R2. Exit 3 is "no Cloudflare token in
# this environment", and the report says so rather than failing the run.
PUB="skipped (no run output)"
if [ -f "$OUT/site/index.html" ]; then
  tools/publish.sh "$OUT" >>"$LOG" 2>&1; p=$?
  case "$p" in 0) PUB="published" ;; 3) PUB="NOT published: $(grep -E "^publish: stopped" "$LOG" | tail -1 | sed "s/^publish: //")" ;; *) PUB="FAILED (exit $p) -- see $LOG" ;; esac
fi
# THE REPORT.
echo "== asset-pulse $DATE: run exit $RUN, $((SECONDS / 60)) min"
grep -E "^backlog:" "$LOG" || echo "backlog: no line (skipped or failed early -- see $LOG)"
echo "history (last two rows):"; tail -n 2 history.csv | sed 's/^/  /'
if [ -f "$OUT/manifest.json" ]; then
  python3 - "$OUT/manifest.json" <<'PY'
import json, sys
m = json.load(open(sys.argv[1]))
bad = [e for e in m if e.get("status") != "ok"]
print("renders: %d subjects, %d not ok" % (len(m), len(bad)))
for e in bad:
    print("  %s: %s" % (e["id"], e["status"]))
PY
fi
[ -f "$OUT/site/index.html" ] && echo "page: $OUT/site/index.html"
[ -f "$OUT/catalog/index.html" ] && echo "catalog: $OUT/catalog/index.html" || echo "catalog: none this run (see bake: lines in $LOG)"
grep -E "^(bake|catalog): " "$LOG" | grep -E "NO IMPOSTOR|GAP|failed|subject\(s\)" | tail -5 | sed 's/^/  /'
echo "publish: $PUB"
echo "pushed: $(git rev-list --count origin/main..HEAD 2>/dev/null) commit(s) not on origin/main (0 is pushed); full log $LOG"
exit $RUN
