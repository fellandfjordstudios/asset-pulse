#!/usr/bin/env python3
"""What the store already held, by subject (tools/cook_hits.py). Run: python tools/test_cook_hits.py"""
import importlib.util
import tempfile
from pathlib import Path

spec = importlib.util.spec_from_file_location("cook_hits", Path(__file__).with_name("cook_hits.py"))
hits = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hits)

with tempfile.TemporaryDirectory() as d:
    store = Path(d)
    for k in ("aa11", "bb22"):
        (store / k[:2] / k).mkdir(parents=True)
    (store / "memo" / "cc" / "cc33").mkdir(parents=True)   # a side record is no bake entry
    before = hits.entries(store)
    assert before == {"aa11", "bb22"}, before
    index = {"rungs": [{"stem": "a", "bake_key": "aa11"}, {"stem": "a", "bake_key": "bb22"},
                       {"stem": "b", "bake_key": "bb22"}, {"stem": "b", "bake_key": "dd44"}],
             "held": [{"stem": "c", "state": "deferred", "why": "deferred: c needs 900 s, 120 s remain"}]}
    lines = hits.report(before, index)
    assert lines[0].startswith("bake: hit  a: 2 rung(s)"), lines
    assert lines[1] == "bake: made b: 1 of 2 rung(s) baked this run", lines
    assert lines[2] == "bake: held c: deferred: c needs 900 s, 120 s remain", lines
    assert lines[-1] == "bake: 1 subject(s) from the store, 1 baked this run, 1 held (deferred or failed)", lines
    # Ablation: an empty "before" (the store not carried) reads every subject as baked.
    assert hits.report(set(), index)[-1].startswith("bake: 0 subject(s) from the store, 2 baked"), "ablation"
print("cook_hits: ok")
