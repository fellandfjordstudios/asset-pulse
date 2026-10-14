#!/bin/bash
# Check out the pinned library under library/, and prove it is the pin.
#
#   tools/sync-library.sh                 sync to library.lock (no-op if current)
#   tools/sync-library.sh --verify        exit 1 unless library/ is the pin, clean
#   tools/sync-library.sh --bump <rev>    re-pin to <rev> (a branch, tag or commit
#                                         on the library's remote), then sync
#
# The pulse is a CONSUMER (fable-plans/active/the-pulse-is-a-consumer in the
# library): every number and every frame it publishes comes from a library tool
# it only calls, under this pin, so a change in the library moves the pulse at
# the next bump and nowhere else. Nothing under library/ is ever edited here.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOCK="$ROOT/library.lock"
LIB="$ROOT/library"
export GIT_TERMINAL_PROMPT=0
die() { echo "sync-library: $*" >&2; exit 1; }
lock_value() {
  local v; v="$(sed -n "s/^$1=//p" "$LOCK")"
  [ -n "$v" ] || die "library.lock has no '$1='"
  printf '%s' "$v"
}
REPO="$(lock_value repo)"
URL="${LIBRARY_URL:-https://github.com/$REPO}"
MODE="sync"; BUMP_REV=""
case "${1:-}" in
  "") ;;
  --verify) MODE="verify" ;;
  --bump) MODE="bump"; BUMP_REV="${2:-}"; [ -n "$BUMP_REV" ] || die "--bump needs a commit, branch or tag" ;;
  *) die "unknown argument: $1" ;;
esac
ensure_checkout() {
  if [ ! -d "$LIB/.git" ]; then
    echo "sync-library: cloning $REPO into library/"
    git clone -q "$URL" "$LIB" || die "clone failed $URL (the library is private: give git a credential)"
  fi
}
if [ "$MODE" = "bump" ]; then
  ensure_checkout
  git -C "$LIB" fetch -q origin "$BUMP_REV" || die "fetch of $BUMP_REV failed"
  NEW="$(git -C "$LIB" rev-parse FETCH_HEAD)"
  OLD="$(lock_value commit)"
  sed -i "s/^commit=.*/commit=$NEW/" "$LOCK"
  echo "sync-library: pin $OLD -> $NEW ($BUMP_REV)"
fi
PIN="$(lock_value commit)"
if [ "$MODE" = "verify" ]; then
  [ -d "$LIB/.git" ] || die "library/ is absent: run tools/sync-library.sh"
  HEAD="$(git -C "$LIB" rev-parse HEAD)"
  [ "$HEAD" = "$PIN" ] || die "library/ is at $HEAD, the pin is $PIN"
  [ -z "$(git -C "$LIB" status --porcelain)" ] || die "library/ has local changes; the pulse never edits the library"
  echo "sync-library: library/ is the pin $PIN, clean"
  exit 0
fi
ensure_checkout
if [ "$(git -C "$LIB" rev-parse HEAD 2>/dev/null || true)" != "$PIN" ]; then
  git -C "$LIB" fetch -q origin "$PIN" 2>/dev/null || git -C "$LIB" fetch -q origin
  git -C "$LIB" checkout -q --detach "$PIN" || die "the pin $PIN is not on the library's remote"
fi
[ -z "$(git -C "$LIB" status --porcelain)" ] || die "library/ has local changes; the pulse never edits the library"
echo "sync-library: library/ at $PIN"
