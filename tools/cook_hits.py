#!/usr/bin/env python3
"""WHAT THE STORE ALREADY HELD, BY SUBJECT (the library's bake plan, step F's gate).

    tools/cook_hits.py before <store> <out.txt>       every bake entry the store holds now
    tools/cook_hits.py report <before.txt> <index.json>

The cook's workers fill the store before its final pass, so the final pass
reads every rung from the store and its own "(cached: ...)" lines cannot tell
a rung baked this run from one an earlier run left. This tells them apart
by the store's entries before the run (`<key[:2]>/<key>`, the library's
AgStore.entry_rel) against the bake keys the cook's index.json ships:

    bake: hit  <stem>: <n> rung(s), every bake key in the store before this run
    bake: made <stem>: <m> of <n> rung(s) baked this run
    bake: held <stem>: <why>                       (the index's held: deferred or failed)

and one line of totals. It reads; it decides nothing about what is baked.
"""
import json
import sys
from pathlib import Path


def entries(store):
    store = Path(store).expanduser()
    if not store.is_dir():
        return set()
    return {e.name for shard in store.iterdir() if shard.is_dir() and len(shard.name) == 2
            for e in shard.iterdir() if e.is_dir()}


def report(before, index):
    rows = {}
    for r in index.get("rungs", []):
        rows.setdefault(r["stem"], []).append(r.get("bake_key", ""))
    lines, hit, made = [], 0, 0
    for stem in sorted(rows):
        keys = rows[stem]
        new = [k for k in keys if k not in before]
        if new:
            made += 1
            lines.append("bake: made %s: %d of %d rung(s) baked this run" % (stem, len(new), len(keys)))
        else:
            hit += 1
            lines.append("bake: hit  %s: %d rung(s), every bake key in the store before this run" % (stem, len(keys)))
    held = index.get("held", [])
    for h in sorted(held, key=lambda h: h.get("stem", "")):
        lines.append("bake: held %s: %s" % (h.get("stem"), h.get("why") or h.get("state")))
    lines.append("bake: %d subject(s) from the store, %d baked this run, %d held (deferred or failed)"
                 % (hit, made, len(held)))
    return lines


def main(argv):
    if len(argv) == 3 and argv[0] == "before":
        Path(argv[2]).write_text("".join(k + "\n" for k in sorted(entries(argv[1]))))
        return 0
    if len(argv) == 3 and argv[0] == "report":
        before = set(Path(argv[1]).read_text().split()) if Path(argv[1]).exists() else set()
        print("\n".join(report(before, json.loads(Path(argv[2]).read_text()))))
        return 0
    sys.exit(__doc__)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
