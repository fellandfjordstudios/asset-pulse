#!/usr/bin/env python3
"""The store kept under the cache's limit (tools/store-prune.py; the library's
plans/062 step 1c). Run: python tools/test_store_prune.py"""
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("store_prune", Path(__file__).with_name("store-prune.py"))
sp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sp)


def entry(store, key, nbytes, age_s):
    e = store / key[:2] / key
    e.mkdir(parents=True)
    f = e / "made.json"
    f.write_bytes(b"x" * nbytes)
    t = 1_700_000_000 - age_s
    os.utime(f, (t, t))
    return e


class Prune(unittest.TestCase):
    def test_the_oldest_go_first_until_it_fits(self):
        with tempfile.TemporaryDirectory() as d:
            s = Path(d)
            old = entry(s, "aa01", 400, 300)
            mid = entry(s / "renders", "bb02", 400, 200)
            new = entry(s, "cc03", 400, 100)
            n, removed, total = sp.prune(s, 900)
            self.assertEqual((n, removed, total), (3, 1, 800))
            self.assertFalse(old.exists())
            self.assertTrue(mid.exists() and new.exists(), "a render entry is aged like a bake's")

    def test_under_the_limit_nothing_goes(self):
        with tempfile.TemporaryDirectory() as d:
            s = Path(d)
            entry(s, "aa01", 100, 10)
            self.assertEqual(sp.prune(s, 1000)[1], 0)

    def test_ablation_without_the_prune_the_store_only_grows(self):
        # THE ABLATION: a limit that is never reached removes nothing, so a
        # store that gains an entry a key and loses none passes 10 GB in time.
        with tempfile.TemporaryDirectory() as d:
            s = Path(d)
            for i in range(5):
                entry(s, "%02d%02d" % (i, i), 300, i)
            self.assertEqual(sp.prune(s, 10 ** 12)[2], 1500)
            self.assertLessEqual(sp.prune(s, 700)[2], 700)


if __name__ == "__main__":
    unittest.main()
