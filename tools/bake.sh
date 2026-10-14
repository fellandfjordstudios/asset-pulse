#!/bin/bash
# THE CATALOG'S BAKE: every rung's glTF and the impostor atlases, made by the
# explorer's own tool exactly as its refresh.sh made them, against the pinned
# library.
#
#   tools/bake.sh                 impostor atlases, then the registry bake with --transfer
#   PULSE_TRANSFER=0 tools/bake.sh   the structural bake only (fast; no baked channel)
#   PULSE_BAKE_BUDGET_S=2700 (with PULSE_RESUME=1)  the whole registry bake in
#                                    that many seconds; what finished is shipped
#   PULSE_RESUME=1 tools/bake.sh     finish a bake cut short (a session's time limit,
#                                    a restart): the atlases are not made again and
#                                    each subject already baked is skipped, kept in
#                                    out/bake-resume/<library>-<explorer>-<mode>/;
#                                    another pin or mode starts fresh
#
# The order is refresh.sh's and it is not arbitrary: `tools/impostor.sh` must run
# before the bake, because the bake only names an atlas already on disk
# (asset-generators defects/017, 018). Both write only the library's
# gitignored build/artifacts/; the library's source tree is never touched, and
# `tools/sync-library.sh --verify` still holds after this.
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
if [ ! -d "$EXP/.git" ]; then
  git clone -q "https://github.com/$REPO" "$EXP" || die "clone of $REPO failed"
fi
if [ "$(git -C "$EXP" rev-parse HEAD)" != "$PIN" ]; then
  git -C "$EXP" fetch -q origin "$PIN" 2>/dev/null || git -C "$EXP" fetch -q origin
  git -C "$EXP" checkout -q --detach "$PIN" || die "the explorer pin $PIN is not on its remote"
fi
[ -z "$(git -C "$EXP" status --porcelain)" ] || die "explorer/ has local changes; the pulse never edits it"
ARGS=(--transfer); [ "${PULSE_TRANSFER:-1}" = "0" ] && ARGS=()
# RESUME (the explorer's bake-library --resume): the artifacts on disk are kept
# only while the record of what made them is, keyed by both pins and the mode.
RESUME_DIR=""
if [ "${PULSE_RESUME:-0}" = "1" ]; then
  RESUME_DIR="$ROOT/out/bake-resume/$(git -C "$LIB" rev-parse --short=12 HEAD)-${PIN:0:12}-${ARGS[*]:-structural}"
  RESUME_DIR="${RESUME_DIR// /}"
fi
if [ -n "$RESUME_DIR" ] && [ -d "$RESUME_DIR" ]; then
  echo "bake: resuming from $RESUME_DIR"
else
  rm -rf "$LIB/build/artifacts" "$ROOT/out/bake-resume"
  [ -z "$RESUME_DIR" ] || mkdir -p "$RESUME_DIR"
fi
if [ -n "$RESUME_DIR" ] && [ -f "$RESUME_DIR/atlases-done" ]; then
  echo "bake: impostor atlases already made for this resume"
else
echo "bake: impostor atlases (the library's tools/impostor.sh)"
# The library's impostor.sh hands `xvfb-run` its `ag_godot` shell function,
# which a child process cannot see (exit 127; filed in the library's feedback/).
# Until it is fixed, the same tool (tools/impostor.gd) is run through the
# library's own display guard, `ag_godot_display`, at impostor.sh's screen size
# and software GL -- the library's functions and settings, nothing chosen here.
( cd "$LIB" && export LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe AG_SCREEN=512x512x24 \
  && source tools/guard.sh && source tools/logdir.sh && source tools/import.sh && ag_import \
  && LOG="$AG_LOGS/impostor.log" && ag_godot_display "$LOG" --path . --rendering-driver opengl3 --script tools/impostor.gd \
  ; code=$?; grep -E "^  " "$AG_LOGS/impostor.log" | tail -3; exit $code ) \
  || echo "bake: NO IMPOSTOR ATLASES this run (the library's tools/impostor.gd failed; see its log); the bake goes on and the catalog names every far rung that lacks one"
[ -z "$RESUME_DIR" ] || touch "$RESUME_DIR/atlases-done"
fi
echo "bake: the registry (the explorer's tools/bake-library.sh ${ARGS[*]:-})"
# WITH RESUME, A CAP: the bake runs under `timeout`, PULSE_BAKE_CAP_S at a time
# (default 2400 s); a run cut by the cap is resumed at once, the subject it was
# on having used one of its two starts (bake-library --resume leaves a subject
# out, by name, after two). One stuck subject then costs two caps, not two
# sessions (2026-10-05: herring, campfire, clinker boat and jetty each spent a
# whole two-hour run). It ends: every cut uses up a start.
registry() { # dir [args]
  local dir=$1; shift
  if [ -z "$RESUME_DIR" ]; then
    LOG="${BAKE_LOG:-$ROOT/out/bake.log}" "$EXP/tools/bake-library.sh" "$LIB" "$@"; return
  fi
  # A BUDGET FOR THE WHOLE BAKE (PULSE_BAKE_BUDGET_S, row 215): past it no
  # subject is begun (bake-library --deadline), a run still going is stopped at
  # it, and one last pass writes the manifest of what finished, the rest named
  # not_baked -- so the catalog deploys with what is done. Unset, no budget.
  local deadline=0 code cap
  [ -z "${PULSE_BAKE_BUDGET_S:-}" ] || deadline=$(( $(date +%s) + PULSE_BAKE_BUDGET_S ))
  local D=(); [ "$deadline" = 0 ] || D=(--deadline "$deadline")
  while :; do
    cap="${PULSE_BAKE_CAP_S:-2400}"
    if [ "$deadline" != 0 ]; then
      local left=$(( deadline - $(date +%s) ))
      if [ "$left" -le 0 ]; then
        echo "bake: the ${PULSE_BAKE_BUDGET_S} s budget is spent; the manifest of what finished"
        LOG="${BAKE_LOG:-$ROOT/out/bake.log}.final" "$EXP/tools/bake-library.sh" "$LIB" "$@" --resume "$RESUME_DIR/$dir" "${D[@]}"
        return
      fi
      [ "$left" -lt "$cap" ] && cap=$left
    fi
    LOG="${BAKE_LOG:-$ROOT/out/bake.log}" timeout "$cap" "$EXP/tools/bake-library.sh" "$LIB" "$@" --resume "$RESUME_DIR/$dir" "${D[@]}"
    code=$?
    [ "$code" = 124 ] || return "$code"
    echo "bake: cut at ${cap} s; resuming (the subject it was on has used a start)"
  done
}
if ! registry registry "${ARGS[@]}"; then
  # The baked-channel bake writes no manifest when any one rung's channel is
  # flat (core/baker.gd flat_channel_problem; filed in the library's feedback/).
  # The library's default bake -- no baked channel, "the Forward+/SDFGI
  # product" -- is still a correct product for a download, so the catalog
  # falls back to it and says so, rather than shipping nothing.
  [ "${#ARGS[@]}" -gt 0 ] || die "the registry bake failed"
  echo "bake: the baked-channel bake FAILED; falling back to the library's default bake (no baked channel)"
  BAKE_LOG="${BAKE_LOG:-$ROOT/out/bake.log}.default" registry default || die "the registry bake failed"
fi
[ -f "$LIB/build/artifacts/manifest.json" ] || die "the bake wrote no manifest"
python3 "$ROOT/tools/catalog_impostors.py" || die "impostor completion failed"
"$ROOT/tools/sync-library.sh" --verify >/dev/null || die "the bake changed the library's source tree"
echo "bake: manifest at $LIB/build/artifacts/manifest.json"
