#!/usr/bin/env python3
"""The bake's ledger of tries (tools/bake_ledger.py). Run: python tools/test_bake_ledger.py"""
import importlib.util
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("bake_ledger", Path(__file__).with_name("bake_ledger.py"))
bl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bl)


class Ledger(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name) / "registry"
        self.d.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def run_bake(self, ledger, keys, began, baked=()):
        """One run: the ledger's presets, then the explorer begins `began`
        (a `.tries` each) and finishes `baked` (an entry each)."""
        failed, _ = bl.before(ledger, keys, [self.d])
        for s in began:
            if s in failed:
                continue  # the explorer leaves it out at its limit
            t = self.d / (s + ".tries")
            t.write_text(str(int(t.read_text()) + 1 if t.exists() else 1))
        for s in baked:
            (self.d / (s + ".entry.json")).write_text("{}")
        return failed, bl.after(ledger, keys, [self.d], "2026-10-24")

    def test_three_tries_then_failed_until_it_changes(self):
        ledger, keys = {}, {"slow": "k1"}
        for n in (1, 2):
            failed, (newly, trying) = self.run_bake(ledger, keys, ["slow"])
            self.assertEqual((failed, newly, trying), ([], [], ["slow"]))
            self.assertEqual(ledger["slow"]["tries"], n)
        failed, (newly, _) = self.run_bake(ledger, keys, ["slow"])
        self.assertEqual(newly, ["slow"])
        # The fourth run leaves it out: the explorer's own limit is written.
        failed, (newly, trying) = self.run_bake(ledger, keys, ["slow"])
        self.assertEqual((failed, newly, trying), (["slow"], [], []))
        self.assertEqual((self.d / "slow.tries").read_text(), bl.EXPLORER_LIMIT)
        self.assertEqual(ledger["slow"]["tries"], 3)
        # Its key moves: it is begun again, from none.
        failed, (newly, trying) = self.run_bake(ledger, {"slow": "k2"}, ["slow"])
        self.assertEqual((failed, trying), ([], ["slow"]))
        self.assertEqual((ledger["slow"]["tries"], ledger["slow"]["key"]), (1, "k2"))

    def test_baked_leaves_the_ledger(self):
        ledger = {}
        self.run_bake(ledger, {"slow": "k1"}, ["slow"])
        self.run_bake(ledger, {"slow": "k1"}, ["slow"], baked=["slow"])
        self.assertEqual(ledger, {})

    def test_a_subject_never_begun_is_not_counted(self):
        ledger = {}
        _, (newly, trying) = self.run_bake(ledger, {}, [])
        self.assertEqual((ledger, newly, trying), ({}, [], []))

    def test_an_unknown_key_is_unchanged(self):
        ledger = {"slow": {"tries": 3, "key": "k1"}}
        failed, _ = bl.before(ledger, {"slow": ""}, [self.d])
        self.assertEqual(failed, ["slow"])

    def test_ablation_without_the_ledger_the_limit_resets(self):
        # The same pin's resume directory keeps the explorer's `.tries`: with
        # the ledger, a subject still trying gets this run's start back.
        (self.d / "slow.tries").write_text("2")
        bl.before({"slow": {"tries": 1, "key": "k1"}}, {"slow": "k1"}, [self.d])
        self.assertFalse((self.d / "slow.tries").exists())


if __name__ == "__main__":
    unittest.main()
