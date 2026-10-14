#!/usr/bin/env python3
"""The guard's cases: fewer subjects keep the live catalog; as many or more
deploy; an unreadable live catalog is kept. `python3 tools/test_catalog_guard.py`"""
import functools
import http.server
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

GUARD = Path(__file__).with_name("catalog_guard.py")


def site(root, n):
    root.mkdir(parents=True, exist_ok=True)
    (root / "index.html").write_text("<main>" + "".join("<div class=card><a href='subject/x%d/'>x</a></div>" % i for i in range(n)) + "</main>")
    return root


def grouped_site(root, n):
    root.mkdir(parents=True, exist_ok=True)
    root.joinpath("index.html").write_text("<main>" + "".join(
        "<article class=card><a data-catalog-entry='entry%d' href='subject/x%d/'>default</a>"
        "<details><a data-catalog-entry='entry%d' href='subject/x%d/variant/'>variant</a></details></article>" % (i, i, i + 1, i)
        for i in range(0, n, 2)) + "</main>")
    return root


def guard(new, live):
    return subprocess.run([sys.executable, str(GUARD), str(new), str(live)], capture_output=True, text=True,
                          env={"PATH": "/usr/bin:/bin", "NO_PROXY": "127.0.0.1", "no_proxy": "127.0.0.1"})


def available_site(root, n, offered, legacy=False):
    root.mkdir(parents=True, exist_ok=True)
    cards = []
    for i in range(n):
        if legacy:
            download = f'<a href="objects/{i}.zip" download="{i}.zip">Free</a>' if i < offered else ''
            cards.append(f'<div class=card>{download}</div>')
        else:
            cards.append(f'<a data-catalog-entry="x{i}" data-downloadable="{str(i < offered).lower()}" href="subject/x{i}/">Asset</a>')
    (root / 'index.html').write_text(''.join(cards))
    return root


def main():
    failed = 0
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        live = site(t / "live", 106)
        # a live site served over HTTP, and the same server's 404 for "no catalog yet"
        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *a):
                pass
        handler = functools.partial(Quiet, directory=str(t))
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        url = "http://127.0.0.1:%d/" % srv.server_port
        cases = [
            ("more preview cards cannot hide lost legacy downloads", available_site(t / "preview-growth", 129, 1), available_site(t / "legacy-downloads", 2, 2, True), 1),
            ("more preview cards cannot hide lost grouped downloads", available_site(t / "preview-growth-2", 129, 1), available_site(t / "grouped-downloads", 4, 2), 1),
            ("discovery can grow while preserving downloads", available_site(t / "complete-growth", 129, 2), available_site(t / "original-downloads", 2, 2, True), 0),
            ("grouped variants preserve 106 entries against 106 legacy cards", grouped_site(t / "grouped", 106), live, 0),
            ("104 grouped entries cannot replace 106 legacy cards", grouped_site(t / "grouped-fewer", 104), live, 1),
            ("a legacy catalog cannot shrink a grouped live catalog", site(t / "old-fewer", 104), grouped_site(t / "grouped-live", 106), 1),
            ("a run with fewer subjects (2 against 106) leaves the live catalog as it was", site(t / "a", 2), live, 1),
            ("as many subjects deploy", site(t / "b", 106), live, 0),
            ("more subjects deploy", site(t / "c", 120), live, 0),
            ("the live catalog over HTTP: fewer subjects keep it", site(t / "f", 2), url + "live/", 1),
            ("the live catalog over HTTP: as many deploy", site(t / "g", 106), url + "live/", 0),
            ("no live catalog yet (404): the first one deploys", site(t / "d", 2), url + "nothing-here/", 0),
            ("ABLATION -- a live catalog that cannot be reached is kept, never replaced", site(t / "e", 2), "http://127.0.0.1:9/", 1),
        ]
        for name, new, lv, want in cases:
            r = guard(new, lv)
            ok = r.returncode == want
            failed += not ok
            print("%s  %s  (%s)" % ("ok  " if ok else "FAIL", name, (r.stdout.strip().splitlines() or [r.stderr.strip()])[-1]))
        srv.shutdown()
    print("%d failed" % failed)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
