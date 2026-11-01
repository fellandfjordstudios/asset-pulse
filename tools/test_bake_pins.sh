#!/usr/bin/env bash
# THE STORE CARRIES THE BAKE ACROSS PINS (the library's bake plan, step F's
# gate; row 712): two bakes in a row, through tools/bake.sh, at two library
# commits, into ONE store. The second logs a hit for every subject whose bake
# keys did not move between the commits and bakes only the rest.
#
#   tools/test_bake_pins.sh <commit A> <commit B> [<generator>...]
#        default generators: stone/pebble built/matchbox
#        LIBRARY_SOURCE=<git dir>   where the commits are fetched from (default
#                                   library/, which holds the pin's history)
#
# Each bake runs in a scratch copy of this repository (tools/, a library.lock
# naming the commit, library/ checked out at it), so the real library/ and its
# pin are never moved. Which keys moved is read from the two cooks' own
# index.json (each rung's bake_key), not assumed: per subject, "same keys"
# must be "bake: hit", and "moved" must be "bake: made".
#   Ablation: the second bake again with PULSE_STORE=0 (a store of its own,
#   the pin-keyed cache's behaviour): every subject is made, and the gate names
#   each one whose keys had not moved.
# Expensive (a cook and the atlases, three times); never part of tools/check.sh.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
A="${1:?usage: tools/test_bake_pins.sh <commit A> <commit B> [<generator>...]}"; B="${2:?commit B}"; shift 2
GENS="${*:-stone/pebble built/matchbox}"
SRC="${LIBRARY_SOURCE:-$ROOT/library}"
export PATH="$HOME/.local/bin:$PATH"
T="$(mktemp -d "${TMPDIR:-/tmp}/pulse-bake-pins.XXXXXX")"
[ -n "${KEEP:-}" ] || trap 'rm -rf "$T"' EXIT
STORE="$T/store"
bake() { # <name> <commit> [env...]: the bake's hits, then its index, kept under $T/<name>
  local name="$1" commit="$2"; shift 2
  local W="$T/$name"
  mkdir -p "$W"
  cp -r "$ROOT/tools" "$W/tools"
  local sha; sha="$(git -C "$SRC" rev-parse --verify "$commit^{commit}")" || return 1
  printf 'repo=%s\ncommit=%s\n' "$(sed -n 's/^repo=//p' "$ROOT/library.lock")" "$sha" > "$W/library.lock"
  git clone -q --shared "$SRC" "$W/library" && git -C "$W/library" checkout -q --detach "$sha" || return 1
  ( cd "$W/library" && godot --headless --path . --import >/dev/null 2>&1 )
  env "$@" AG_BAKE_CACHE="$STORE" PULSE_BAKE_ONLY="$GENS" BAKE_LOG="$W/bake.log" "$W/tools/bake.sh" > "$W/out.txt" 2>&1
  echo $? > "$W/code"
}
keys() { python3 -c '
import json, sys
ix = json.load(open(sys.argv[1]))
k = {}
for r in ix.get("rungs", []):
    k.setdefault(r["stem"], []).append(r.get("bake_key", ""))
print(json.dumps({s: sorted(v) for s, v in k.items()}))' "$1/out/cooked/catalog/index.json" 2>/dev/null || echo '{}'; }
# judge <first> <second>: per subject, its keys moved or not, against hit or made
judge() { python3 - "$(keys "$T/$1")" "$(keys "$T/$2")" "$T/$2/bake.log.hits" <<'PY'
import json, re, sys
a, b = json.loads(sys.argv[1]), json.loads(sys.argv[2])
said = {}
for l in open(sys.argv[3]) if b else []:
    m = re.match(r"bake: (hit|made) +([^:]+):", l)
    if m:
        said[m.group(2).strip()] = m.group(1)
bad, same, moved = [], [], []
for s in sorted(b):
    if s not in a:
        continue
    want = "hit" if a[s] == b[s] else "made"
    (same if want == "hit" else moved).append(s)
    if said.get(s) != want:
        bad.append("%s: keys %s, logged %s" % (s, "same" if want == "hit" else "moved", said.get(s, "nothing")))
print("%d same (%s), %d moved (%s)%s" % (len(same), ",".join(same), len(moved), ",".join(moved),
      "; WRONG: " + "; ".join(bad) if bad else ""))
sys.exit(1 if bad or not b else 0)
PY
}
fails=0
say() { if [ "$1" = 0 ]; then echo "  ok   $2"; else echo "  FAIL $2"; fails=$((fails + 1)); fi; }
bake first "$A"
[ "$(cat "$T/first/code")" = 0 ]; say $? "the bake at $A (exit $(cat "$T/first/code"); $(grep -E '^bake: [0-9]+ subject' "$T/first/bake.log.hits" | tail -1))"
bake second "$B"
r="$(judge first second)"; say $? "the bake at $B into the same store: a hit for each subject whose keys stayed, made for each that moved -- $r"
bake ablation "$B" PULSE_STORE=0
r="$(judge first ablation)"; case "$r" in *WRONG*"keys same, logged made"*) true ;; *) false ;; esac; say $? "ABLATION -- a store of its own (PULSE_STORE=0) rebakes the subjects whose keys stayed -- $r"
if [ "$fails" != 0 ]; then for n in first second ablation; do echo "== $n"; tail -20 "$T/$n/out.txt" 2>/dev/null | sed 's/^/    /'; done; fi
echo "test_bake_pins: $fails failed"
exit $((fails > 0))
