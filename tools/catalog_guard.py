#!/usr/bin/env python3
"""THE PUBLIC CATALOG NEVER SHRINKS BY ACCIDENT (row 215, option A, the owner
2026-10-10): a run's catalog is deployed only when it lists at least as many
subjects as the one live now. A run cut short by the registry bake's budget
(the glTF surface bake, asset-generators 49cf1557) ships a catalog of what
finished; this keeps the fuller live one instead.

    tools/catalog_guard.py <new catalog dir> <live catalog URL or dir>

Exit 0: deploy (prints both counts). Exit 1: keep the live one. No live page
(404: the first deploy, Pages just turned on) counts as zero, so the first
catalog always deploys; a live page that cannot be read for any other reason
(the network, a 5xx) keeps it, since a fuller catalog may be behind the error. An entry is one marked stable subject link on the new index, or one
`<div class=card>` on the legacy index. Grouping variants never changes the unit.
"""
import re
from html.parser import HTMLParser
import sys
import urllib.error
import urllib.request
from pathlib import Path

CARD = re.compile(r"<div class=card>")


def count(html):
    class Entries(HTMLParser):
        def __init__(self):
            super().__init__()
            self.keys = set()
        def handle_starttag(self, tag, attrs):
            key = dict(attrs).get("data-catalog-entry")
            if tag == "a" and key:
                self.keys.add(key)
    entries = Entries()
    entries.feed(html or "")
    # Old live catalogs count one div per bake entry. New catalogs group
    # variants but mark one stable link per entry, preserving the same unit.
    return len(entries.keys) if entries.keys else len(CARD.findall(html or ""))


def downloads(html):
    """Preview-only cards must not conceal loss of existing downloads."""
    class Downloads(HTMLParser):
        def __init__(self):
            super().__init__()
            self.keys = set()
        def handle_starttag(self, tag, attrs):
            if tag != "a":
                return
            attrs = dict(attrs)
            if attrs.get("data-downloadable") == "true":
                self.keys.add(attrs.get("data-catalog-entry"))
            elif "download" in attrs and attrs.get("href", "").endswith(".zip"):
                self.keys.add(attrs["href"])
    parser = Downloads()
    parser.feed(html or "")
    return len(parser.keys)


def read(where):
    if not where.startswith(("http://", "https://")):
        f = Path(where) / "index.html"
        return f.read_text(encoding="utf-8") if f.exists() else ""
    try:
        with urllib.request.urlopen(where.rstrip("/") + "/", timeout=30) as r:
            return r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print("catalog-guard: no live catalog (404); counting it as 0")
            return ""
        raise SystemExit("catalog-guard: KEEP the live catalog -- it could not be read (HTTP %d)" % e.code)
    except Exception as e:  # noqa: BLE001
        raise SystemExit("catalog-guard: KEEP the live catalog -- it could not be read (%s)" % e)


def main(argv):
    if len(argv) != 3:
        sys.exit(__doc__)
    new_html, live_html = read(str(argv[1])), read(str(argv[2]))
    new, live = count(new_html), count(live_html)
    new_downloads, live_downloads = downloads(new_html), downloads(live_html)
    if new_downloads < live_downloads:
        print("catalog-guard: KEEP the live catalog -- %d downloads now, %d live" % (new_downloads, live_downloads))
        return 1
    if new >= live:
        print("catalog-guard: deploy -- %d subject(s) now, %d live" % (new, live))
        return 0
    print("catalog-guard: KEEP the live catalog -- this run has %d subject(s), the live one %d" % (new, live))
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
