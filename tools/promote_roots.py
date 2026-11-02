#!/usr/bin/env python3
"""THE STORE, PUT TO THE GLOBAL CACHE (the library's row 724; its plans/111).

    tools/promote_roots.py <run dir> <library> <store>

Every root a cook of this run published -- the library's cook prints
`ROOT <hash>` when it writes a store, a root naming each entry it read or made
with the memo records a cook keys its rungs from -- is promoted to the
library's cache Worker with every entry it names, by the library's own tool
(`<library>/tools/store.sh promote <store> --root <hash> --to <url>`). The
roots are read from the run's logs (`<run dir>/*.log`). The Worker keeps an
entry it holds (create-if-absent), so promoting again sends nothing.

CACHE_TOKEN (an Actions secret: the Worker's writer token, its SHA-256 in the
Worker's PUBLISH_TOKEN_SHA256) is read from the environment and never printed;
with none, it says so and exits 0. CACHE_URL overrides the Worker. A root the
Worker refuses is named, and the exit is 1.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

CACHE_URL = "https://cache.johnnyillinois.workers.dev"
ROOT_LINE = re.compile(r"^\s*ROOT ([0-9a-f]{64})\s*$")


def roots_in(run_dir):
    """Each root the run's logs name, in the order first seen."""
    seen = []
    for log in sorted(Path(run_dir).glob("*.log")):
        for line in log.read_text(errors="replace").splitlines():
            m = ROOT_LINE.match(line)
            if m and m.group(1) not in seen:
                seen.append(m.group(1))
    return seen


def main(argv, environ=os.environ, run=subprocess.run):
    if len(argv) != 3:
        print(__doc__)
        return 2
    run_dir, library, store = argv
    roots = roots_in(run_dir)
    if not roots:
        print("promote: no root in this run's logs (no cook wrote the store)")
        return 0
    if not environ.get("CACHE_TOKEN"):
        print("promote: %d root(s) not put to the global cache: no CACHE_TOKEN secret (the owner's to add)" % len(roots))
        return 0
    url = environ.get("CACHE_URL", CACHE_URL)
    bad = 0
    for h in roots:
        r = run(["bash", str(Path(library) / "tools/store.sh"), "promote", str(store), "--root", h, "--to", url],
                env=dict(environ), capture_output=True, text=True)
        tail = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()[-1:] or [""]
        print("promote: root %s %s: %s" % (h[:12], "promoted" if r.returncode == 0 else "REFUSED", tail[0][:300]))
        bad += r.returncode != 0
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
