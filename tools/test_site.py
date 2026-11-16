"""THE PRIVATE PAGE'S BAND TABLE READS THE LIBRARY'S SHEET AS IT IS NOW.

Run 80 (2026-11-15) failed in tools/site.py on KeyError 'error_px': the
library's rung sheet writes `outline_px` since its row 781, and may write it
null (not judged). The table reads either, and shows a null as "--".
"""
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("pulse_site", Path(__file__).with_name("site.py"))
site = importlib.util.module_from_spec(spec)
spec.loader.exec_module(site)


class BandTable(unittest.TestCase):
    def test_outline_px_as_the_sheet_writes_it_now(self):
        band = {"band": 0, "from_m": 1.0, "rung": 0, "how": "mesh", "cost": 100, "ceiling": 200,
                "outline_px": 0.25, "derived": {"verdict": "ok", "cost": 50, "outline_px": 0.4}, "saved": 50}
        table = site.band_table([band])
        self.assertIn("<td>0.25</td>", table)
        self.assertIn("<td>0.40</td>", table)

    def test_a_null_outline_is_not_judged(self):
        band = {"band": 0, "from_m": 1.0, "rung": 0, "how": "mesh", "cost": 100, "ceiling": 200,
                "outline_px": None, "derived": {}}
        self.assertIn("<td>--</td>", site.band_table([band]))

    def test_an_older_sheet_with_error_px(self):
        band = {"band": 1, "from_m": 2.0, "rung": 1, "how": "mesh", "cost": 10, "ceiling": 20, "error_px": 0.7}
        self.assertIn("<td>0.70</td>", site.band_table([band]))


if __name__ == "__main__":
    unittest.main()
