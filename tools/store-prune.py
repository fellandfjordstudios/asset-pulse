#!/usr/bin/env python3
"""THE STORE, UNDER THE CACHE'S LIMIT (the library's plans/062 step 1c).

    tools/store-prune.py <store> [--max-gb 6]

The store (the library's ~/.cache/asset-generators/bakes) gains an entry for
every key a run makes and loses none, and GitHub's cache holds 10 GB a
repository. Past --max-gb, the entries made longest ago are removed until it
fits: an entry is a directory two levels down (<key[:2]>/<key>, renders under
renders/), aged by its newest file. What is removed is only made again when
asked for.
"""
import shutil
import sys
from pathlib import Path


def entries(store):
    for top in [store, store / "renders"]:
        if not top.is_dir():
            continue
        for shard in top.iterdir():
            if shard.is_dir() and len(shard.name) == 2:
                for e in shard.iterdir():
                    if e.is_dir():
                        yield e


def size(p):
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def prune(store, max_bytes):
    rows = []
    for e in entries(store):
        files = [f for f in e.rglob("*") if f.is_file()]
        rows.append((max((f.stat().st_mtime for f in files), default=0.0), size(e), e))
    total = sum(r[1] for r in rows)
    removed = 0
    for _, b, e in sorted(rows):
        if total <= max_bytes:
            break
        shutil.rmtree(e, ignore_errors=True)
        total -= b
        removed += 1
    return len(rows), removed, total


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        sys.exit(__doc__)
    store = Path(argv[0]).expanduser()
    max_gb = float(argv[argv.index("--max-gb") + 1]) if "--max-gb" in argv else 6.0
    if not store.is_dir():
        print("store-prune: no store at %s" % store)
        return 0
    n, removed, total = prune(store, int(max_gb * 1e9))
    print("store-prune: %d entries, %d removed, %.2f GB kept (limit %.1f GB)" % (n, removed, total / 1e9, max_gb))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
