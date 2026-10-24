#!/usr/bin/env python3
"""THE BAKE'S LEDGER OF TRIES (the owner, 2026-10-24: "if the build times out
because an expensive uncached generator started late in the build, I'd like
for it to try again ... Maybe try it 3x, then mark it failed and don't try
again until it changes").

    tools/bake_ledger.py stems <ledger>                       the stems it holds
    tools/bake_ledger.py before <ledger> <keys.json> <dir>... before the bake
    tools/bake_ledger.py started <ledger> <dir>...            the stems this run began and did not finish
    tools/bake_ledger.py after <ledger> <keys.json> <dir>...  after the bake

Each <dir> is a resume directory of the explorer's bake-library --resume:
`<stem>.entry.json` for a subject baked, `<stem>.tries` for one begun. A
subject begun in a run and not finished -- cut by the budget, a hang, a bake
with problems -- has used one of its PULSE_BAKE_TRIES (3) tries, recorded
under its bake key (tools/bake_keys.gd: the library's own keys). One that
has used them all is FAILED: before the bake its `.tries` is set to the
explorer's own limit, so the explorer leaves it out by name (`not_baked`)
and the rest of the bake goes on; it is tried again, from none, the day its
key moves. A subject baked leaves the ledger. A subject the budget never
reached is not counted: it is first in line the next run, when the subjects
before it come from the store.

A key of "" (it could not be made in time) is taken as unchanged.
"""
import datetime
import json
import os
import sys
from pathlib import Path

TRIES = 3
EXPLORER_LIMIT = "2"  # bake-library --resume leaves a subject out after two starts


def load(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}


def save(path, ledger):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(ledger, indent=1, sort_keys=True) + "\n")
    tmp.replace(path)


def changed(row, key):
    return key != "" and row.get("key", "") != "" and key != row["key"]


def failed(row, tries=TRIES):
    return row.get("tries", 0) >= tries


def before(ledger, keys, dirs, tries=TRIES):
    """Each subject the ledger holds gets this run's start, or is left out as
    failed; a subject whose key moved starts again from none. Returns
    (the failed, the tried again because they changed)."""
    out, again = [], []
    for stem, row in sorted(ledger.items()):
        key = keys.get(stem, "")
        if changed(row, key):
            row.update(tries=0, key=key)
            again.append(stem)
        for d in dirs:
            p = Path(d) / (stem + ".tries")
            if failed(row, tries):
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(EXPLORER_LIMIT)
            else:
                p.unlink(missing_ok=True)
        if failed(row, tries):
            out.append(stem)
    return out, again


def started(ledger, dirs, tries=TRIES):
    """The subjects begun in these directories and not finished, the failed
    (whose `.tries` the ledger wrote) aside."""
    out = set()
    for d in dirs:
        d = Path(d)
        if not d.is_dir():
            continue
        for t in d.glob("*.tries"):
            stem = t.name[: -len(".tries")]
            if (d / (stem + ".entry.json")).exists():
                continue
            if failed(ledger.get(stem, {}), tries):
                continue
            out.add(stem)
    return sorted(out)


def after(ledger, keys, dirs, today, tries=TRIES):
    """Count this run's tries; a subject baked leaves the ledger. Returns
    (the newly failed, the still trying)."""
    began = started(ledger, dirs, tries)
    for d in dirs:
        d = Path(d)
        for e in d.glob("*.entry.json") if d.is_dir() else []:
            ledger.pop(e.name[: -len(".entry.json")], None)
    newly, trying = [], []
    for stem in began:
        row = ledger.setdefault(stem, {"tries": 0, "key": ""})
        row["tries"] = row.get("tries", 0) + 1
        row["last"] = today
        if keys.get(stem, ""):
            row["key"] = keys[stem]
        (newly if failed(row, tries) else trying).append(stem)
    return newly, trying


def main(argv):
    if len(argv) < 2 or argv[0] not in ("stems", "before", "started", "after"):
        sys.exit(__doc__)
    cmd, path = argv[0], argv[1]
    ledger = load(path)
    tries = int(os.environ.get("PULSE_BAKE_TRIES", TRIES))
    if cmd == "stems":
        print(" ".join(sorted(ledger)))
        return 0
    if cmd == "started":
        print(" ".join(started(ledger, argv[2:], tries)))
        return 0
    keys = load(argv[2])
    if cmd == "before":
        out, again = before(ledger, keys, argv[3:], tries)
        save(path, ledger)
        for s in again:
            print("bake: %s changed since it failed; it is tried again" % s)
        for s in out:
            r = ledger[s]
            print("bake: FAILED %s: begun %d times and never finished (last %s); not tried again until it changes"
                  % (s, r["tries"], r.get("last", "?")))
        return 0
    newly, trying = after(ledger, keys, argv[3:], datetime.date.today().isoformat(), tries)
    save(path, ledger)
    for s in trying:
        print("bake: %s begun and not finished, try %d of %d; tried again next run" % (s, ledger[s]["tries"], tries))
    for s in newly:
        print("bake: FAILED %s: begun %d times and never finished; not tried again until it changes" % (s, ledger[s]["tries"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
