#!/bin/bash
# THE DERIVATION BACKLOG, PAID ONCE AND KEPT HERE (the owner, 2026-10-02: "let
# asset pulse fix the derivation ... I don't want to pay twice for a super
# expensive job"; and 2026-10-23: "Why not have the asset generators library
# pull from the asset pulse results. Pushing into an already hard to coordinate
# repo seems backwards").
#
# The library's expensive searches -- the derivation benchmark, the goal table,
# every derived record and drawn ladder another deriver wrote -- run here by the
# library's own steps (`tools/derive-backlog.sh`'s, records first). What it finishes
# is KEPT IN THIS REPOSITORY, on the branch `derive-results`, laid out as the
# library's tree, with `manifest.json`; nothing is pushed to the library. The
# library takes from there what is current for it (its `tools/derive-pull.sh`),
# and transect gets it with its ordinary library bump.
#
# RESUMED, NEVER PAID TWICE: the results kept so far are laid over library/
# first, so a record already derived for this deriver and generator is not
# stale and is not searched again; the bench's checkpoints and the records'
# parts live in library/.git/ag-logs, which the workflow keeps in actions/cache.
# The job runs inside PULSE_BACKLOG_BUDGET_S (default 5 h), so a backlog longer
# than one runner's limit stops cleanly, keeps every file it finished, and the
# next run resumes. library/ is put back at its pin at the end: the pulse never
# leaves the library edited.
#
#   tools/backlog.sh          run it, keep what it finished on derive-results
#   tools/backlog.sh --list   what is on the backlog, nothing run
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LIB="$ROOT/library"
DATE="$(date -u +%Y-%m-%d)"
BRANCH="${PULSE_RESULTS_BRANCH:-derive-results}"
KEEP="$ROOT/out/derive-results"
[ -d "$LIB/.git" ] || { echo "backlog: no library/ -- run tools/sync-library.sh"; exit 1; }
if [ "${1:-}" = "--list" ]; then
  ( cd "$LIB" && tools/derive-backlog.sh --list )
  exit $?
fi
PIN="$(git -C "$LIB" rev-parse HEAD)"
# WHAT THE JOB WRITES THAT IS KEPT: the two tables and the records beside the
# generators and fixtures (a pathspec `*` crosses directories). Anything else it
# writes is not the pulse's to keep.
kept_paths() {
  git -C "$LIB" status --porcelain --untracked-files=all -- test/derive_bench.json test/derive_goal.json \
    'generators/*.derived.json' 'generators/*.drawn.json' 'test/fixtures/*.derived.json' \
    | grep -v '^ D \|^D  ' | sed 's/^...//'
}
restore_library() {
  git -C "$LIB" checkout -q -- . && git -C "$LIB" clean -fdq -- generators test
}
# THE RESULTS SO FAR, as a worktree of this repository's results branch.
rm -rf "$KEEP"; git -C "$ROOT" worktree prune
if git -C "$ROOT" fetch -q origin "$BRANCH" 2>/dev/null; then
  git -C "$ROOT" worktree add -q -f --detach "$KEEP" FETCH_HEAD || { echo "backlog: could not check out $BRANCH"; exit 1; }
else
  git -C "$ROOT" worktree add -q -f --detach "$KEEP" HEAD || { echo "backlog: could not make a worktree"; exit 1; }
  ( cd "$KEEP" && git checkout -q --orphan "pulse-$BRANCH" && git rm -rqf . )
  echo "backlog: no $BRANCH yet -- it starts here"
fi
# LAID OVER library/: what an earlier run finished is current, so not searched again.
laid=0
while IFS= read -r rel; do
  mkdir -p "$LIB/$(dirname "$rel")" && cp "$KEEP/$rel" "$LIB/$rel" && laid=$((laid + 1))
done < <(cd "$KEEP" && find generators test -type f \( -name '*.derived.json' -o -name '*.drawn.json' -o -name 'derive_goal.json' -o -name 'derive_bench.json' \) 2>/dev/null)
echo "backlog: $laid file(s) kept by earlier runs laid over library/ at ${PIN:0:12}"
BUDGET="${PULSE_BACKLOG_BUDGET_S:-18000}"
SECONDS=0
# THE LIBRARY'S OWN STEPS, RECORDS FIRST (`tools/derive-backlog.sh`'s, in the
# library, run here one by one): the stale derived records -- what the game
# builds from, each written whole as it finishes and each re-checked from its
# recorded winner, never from the tables -- then the build records and the
# drawn ladders, then the benchmark and the goal table, which write nothing
# until every job is done. Run in the library's order, the first run spent its
# whole 5 h 10 min inside the benchmark and kept nothing (10-23); in this one,
# what a budget cuts short is the tables, and their checkpoints resume.
how="cleared"
step() {
  local name="$1"; shift
  local left=$((BUDGET - SECONDS))
  if [ "$left" -le 60 ]; then how="stopped at the budget (${BUDGET} s) before $name; the next run resumes"; return 1; fi
  ( cd "$LIB" && AG_RUNNER=1 timeout --signal=TERM --kill-after=120 "$left" "$@" )
  local code=$?
  case "$code" in
    0) echo "backlog: $name done at ${SECONDS}s" ;;
    124|137) how="stopped at the budget (${BUDGET} s) in $name; the next run resumes"; return 1 ;;
    *) how="failed in $name (exit $code); what it finished is kept"; return 1 ;;
  esac
}
step "the stale records" tools/derive.sh --stale \
  && step "the build records" bash -c 'tools/build-times.sh --stale && tools/ladder-records.sh && tools/cards.sh' \
  && step "the drawn ladders" tools/drawn-ladder.sh --stale \
  && step "the benchmark and the goal table" env DERIVE_BENCH_BOTH=1 tools/derive-bench.sh
echo "backlog: the library's steps $how after ${SECONDS}s"
# KEPT: every file written whole -- a file the budget cut mid-write does not
# parse, and is left out.
n=0; bad=0
while IFS= read -r rel; do
  [ -n "$rel" ] || continue
  if ! python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$LIB/$rel" 2>/dev/null; then
    bad=$((bad + 1)); continue
  fi
  mkdir -p "$KEEP/$(dirname "$rel")" && cp "$LIB/$rel" "$KEEP/$rel" && n=$((n + 1))
done < <(kept_paths)
LEFT="$( (cd "$LIB" && tools/derive-backlog.sh --list 2>/dev/null) | grep -E 'record\(s\) on the' | sed 's/^ *//' | paste -sd ';' -)"
restore_library
python3 - "$KEEP/manifest.json" "$PIN" "$how" "$LEFT" <<'EOF'
import json, os, sys, datetime
path, pin, how, left = sys.argv[1:5]
run = os.environ.get("GITHUB_RUN_ID")
m = {"library": pin, "written_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
     "job": how, "backlog_left": left}
if run:
    m["run"] = "%s/%s/actions/runs/%s" % (os.environ.get("GITHUB_SERVER_URL", "https://github.com"),
                                          os.environ.get("GITHUB_REPOSITORY", ""), run)
open(path, "w").write(json.dumps(m, indent=1, sort_keys=True) + "\n")
EOF
cd "$KEEP"
git add -A
if git diff --cached --quiet -- generators test; then
  echo "backlog: nothing new to keep ($n file(s) written, all as kept before; $bad cut mid-write)"
  exit 0
fi
git commit -q -m "derivation results at library ${PIN:0:12}, $DATE" \
  -m "$n file(s) written whole by tools/derive-backlog.sh, $bad cut mid-write and left out; the job $how. Left on the backlog: ${LEFT:-unknown}." \
  || { echo "backlog: commit failed"; exit 1; }
for i in 1 2 3; do
  git push -q origin "HEAD:refs/heads/$BRANCH" && { echo "backlog: kept $n file(s) on $BRANCH at $(git rev-parse --short HEAD)"; exit 0; }
  sleep 5
done
echo "backlog: could not push $BRANCH; the results are in $KEEP"
exit 1
