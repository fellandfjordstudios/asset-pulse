#!/usr/bin/env python3
"""tools/promote_roots.py: the roots read from a run's logs, each promoted by the
library's store.sh with the token, none without it, a refusal named."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import promote_roots  # noqa: E402

A, B = "a" * 64, "b" * 64
failed = 0


def check(cond, what):
    global failed
    if not cond:
        failed += 1
        print("FAIL " + what)


class Done:
    def __init__(self, code):
        self.returncode, self.stdout, self.stderr = code, "ok\n", ""


with tempfile.TemporaryDirectory() as d:
    Path(d, "bake.log").write_text("cooking\n  ROOT %s\nROOT %s\nROOT %s\nROOTS nothing\n" % (A, B, A))
    Path(d, "other.txt").write_text("ROOT %s\n" % ("c" * 64))
    check(promote_roots.roots_in(d) == [A, B], "the roots read from the logs: %s" % promote_roots.roots_in(d))
    calls = []
    def run(cmd, **kw):
        calls.append((cmd, kw["env"].get("CACHE_TOKEN"), "CLOUDFLARE_API_TOKEN" in kw["env"]))
        return Done(0)
    check(promote_roots.main([d, "lib", "store"], {}, run) == 0 and calls == [], "a run with no token promoted")
    check(promote_roots.main([d, "lib", "store"], {"CLOUDFLARE_API_TOKEN": "t"}, run) == 0, "a promotion that passed failed")
    check([c[0][2:6] for c in calls] == [["promote", "store", "--root", A], ["promote", "store", "--root", B]],
          "store.sh not called once a root: %s" % calls)
    check(all(c[0][-1] == promote_roots.CACHE_URL and c[1] == "t" for c in calls), "the Worker or the token not passed")
    check(not any(c[2] for c in calls), "the Cloudflare token reached the library's tool under its own name too")
    calls.clear()
    check(promote_roots.main([d, "lib", "store"], {"CACHE_TOKEN": "declined"}, run) == 0 and calls == [],
          "a CACHE_TOKEN alone promoted: the bearer is the account's Cloudflare token")
    check(promote_roots.main([d, "lib", "store"], {"CLOUDFLARE_API_TOKEN": "t"}, lambda c, **k: Done(1)) == 1,
          "a root the Worker refused was not a failure")
with tempfile.TemporaryDirectory() as d:
    check(promote_roots.main([d, "lib", "store"], {"CLOUDFLARE_API_TOKEN": "t"}, run) == 0, "a run with no root failed")

print("promote_roots: %s" % ("ok" if not failed else "%d FAILED" % failed))
sys.exit(1 if failed else 0)
