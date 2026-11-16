#!/usr/bin/env bash
# Check out the pinned library under library/, and prove it is the pin.
#
#   tools/sync-library.sh                 sync to library.lock (no-op if current)
#   tools/sync-library.sh --verify        exit 1 unless library/ is the pin, clean
#   tools/sync-library.sh --bump <rev>    re-pin to <rev> (a branch, tag or commit
#                                         on the library's remote), then sync;
#                                         the catalogue (catalogue.lock) moves to
#                                         its main with it
#
# THE CATALOGUE BESIDE THE LIBRARY. Generators are moving from the library to
# the catalogue repository the library names (its ops/catalogue-moved.json).
# catalogue.lock pins it; its own
# files (generators/, and the floors and baselines it owns under test/) are laid
# over library/ at the same paths and listed in library/.git/info/exclude, so the
# checkout stays the clean pin plus the catalogue's subjects. A catalogue file the
# pinned library ALSO holds (a pin older than the move) is left as the library's.
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
  # BSD sed (macOS) needs a suffix after -i; GNU takes it too (transect's form).
  sed -i.bak "s/^commit=.*/commit=$NEW/" "$LOCK" && rm -f "$LOCK.bak"
  echo "sync-library: pin $OLD -> $NEW ($BUMP_REV)"
fi
PIN="$(lock_value commit)"

# --------------------------------------------------------------- the catalogue
CLOCK="$ROOT/catalogue.lock"
CAT="$ROOT/catalogue"
OVERLAY="$LIB/.git/info/catalogue-overlay"
cat_value() { sed -n "s/^$1=//p" "$CLOCK"; }
catalogue_pin() {
  CREPO="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("repository",""))' "$LIB/ops/catalogue-moved.json" 2>/dev/null || true)"
  CURL="${CATALOGUE_URL:-https://github.com/$CREPO}"
  CPIN="$(cat_value commit)"
}
catalogue_verify() {
  [ -f "$CLOCK" ] || return 0
  catalogue_pin
  [ -n "$CREPO" ] || return 0
  [ -n "$CPIN" ] || die "catalogue.lock has no commit: run tools/sync-library.sh --bump main"
  [ -d "$CAT/.git" ] || die "catalogue/ is absent: run tools/sync-library.sh"
  [ "$(git -C "$CAT" rev-parse HEAD)" = "$CPIN" ] || die "catalogue/ is not the pin $CPIN"
  [ -f "$OVERLAY" ] || die "the catalogue is not laid over library/: run tools/sync-library.sh"
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    cmp -s "$CAT/$f" "$LIB/$f" || die "library/$f is not the catalogue's at $CPIN"
  done < "$OVERLAY"
  echo "sync-library: catalogue/ is the pin $CPIN, $(wc -l < "$OVERLAY" | tr -d ' ') file(s) laid over library/"
}
catalogue_sync() {
  [ -f "$CLOCK" ] || return 0
  catalogue_pin
  if [ -z "$CREPO" ]; then
    echo "sync-library: the library at $PIN names no catalogue (no ops/catalogue-moved.json): nothing to lay over"
    return 0
  fi
  if [ ! -d "$CAT/.git" ]; then
    echo "sync-library: cloning $CREPO into catalogue/"
    git clone -q "$CURL" "$CAT" || die "clone failed $CURL (the catalogue is private: give git a credential)"
  fi
  if [ "$MODE" = "bump" ]; then
    git -C "$CAT" fetch -q origin main || die "fetch of the catalogue's main failed"
    CPIN="$(git -C "$CAT" rev-parse FETCH_HEAD)"
    sed -i.bak "s/^commit=.*/commit=$CPIN/" "$CLOCK" && rm -f "$CLOCK.bak"
    echo "sync-library: catalogue pin -> $CPIN"
  fi
  [ -n "$CPIN" ] || die "catalogue.lock has no commit: run tools/sync-library.sh --bump main"
  if [ "$(git -C "$CAT" rev-parse HEAD 2>/dev/null || true)" != "$CPIN" ]; then
    git -C "$CAT" fetch -q origin "$CPIN" 2>/dev/null || git -C "$CAT" fetch -q origin
    git -C "$CAT" checkout -q --detach "$CPIN" || die "the catalogue pin $CPIN is not on its remote"
  fi
  local excl="$LIB/.git/info/exclude" f
  if [ -f "$OVERLAY" ]; then
    while IFS= read -r f; do [ -n "$f" ] && rm -f "$LIB/$f"; done < "$OVERLAY"
    if [ -f "$excl" ]; then
      grep -vxF -f <(sed 's|^|/|' "$OVERLAY") "$excl" > "$excl.new" || true; mv "$excl.new" "$excl"
    fi
  fi
  # Its own files: generators and the test/ evidence it owns; never its tooling.
  : > "$OVERLAY.new"
  while IFS= read -r f; do
    git -C "$LIB" cat-file -e "HEAD:$f" 2>/dev/null && continue
    mkdir -p "$LIB/$(dirname "$f")" && cp "$CAT/$f" "$LIB/$f" && echo "$f" >> "$OVERLAY.new"
  done < <(git -C "$CAT" ls-files -- generators test)
  mv "$OVERLAY.new" "$OVERLAY"
  sed 's|^|/|' "$OVERLAY" >> "$excl"
  [ -z "$(git -C "$LIB" status --porcelain)" ] || die "library/ is not clean after laying the catalogue over it"
  echo "sync-library: catalogue/ at $CPIN, $(wc -l < "$OVERLAY" | tr -d ' ') file(s) laid over library/"
}
if [ "$MODE" = "verify" ]; then
  [ -d "$LIB/.git" ] || die "library/ is absent: run tools/sync-library.sh"
  HEAD="$(git -C "$LIB" rev-parse HEAD)"
  [ "$HEAD" = "$PIN" ] || die "library/ is at $HEAD, the pin is $PIN"
  [ -z "$(git -C "$LIB" status --porcelain)" ] || die "library/ has local changes; the pulse never edits the library"
  echo "sync-library: library/ is the pin $PIN, clean"
  catalogue_verify
  exit 0
fi
ensure_checkout
if [ "$(git -C "$LIB" rev-parse HEAD 2>/dev/null || true)" != "$PIN" ]; then
  git -C "$LIB" fetch -q origin "$PIN" 2>/dev/null || git -C "$LIB" fetch -q origin
  git -C "$LIB" checkout -q --detach "$PIN" || die "the pin $PIN is not on the library's remote"
fi
[ -z "$(git -C "$LIB" status --porcelain)" ] || die "library/ has local changes; the pulse never edits the library"
echo "sync-library: library/ at $PIN"
catalogue_sync
