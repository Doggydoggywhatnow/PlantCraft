"""Offline tests: python3 -m unittest discover -s pipeline/tests   (run from the repo root)"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import extract
from common import species_id


class Verify(unittest.TestCase):
    TEXT = "Pedunculate oak is a deciduous tree, typically up to 20 m in height – sometimes 40 m."

    def test_exact_quote_kept(self):
        kept, dropped = extract.verify({"life_form": {"value": "tree", "quote": "is a deciduous tree"}}, self.TEXT)
        self.assertIn("life_form", kept)
        self.assertEqual(dropped, [])

    def test_whitespace_and_dash_normalised(self):
        q = "typically up to 20 m in height  - sometimes 40 m"
        kept, _ = extract.verify({"height_cm": {"max": 4000, "quote": q}}, self.TEXT)
        self.assertIn("height_cm", kept)

    def test_invented_quote_dropped(self):
        kept, dropped = extract.verify({"environment": {"value": "swamp", "quote": "grows in swamps"}}, self.TEXT)
        self.assertEqual(kept, {})
        self.assertEqual(dropped, ["environment"])

    def test_uses_filtered_individually(self):
        facts = {"uses_real": [{"use": "timber", "note": "x", "quote": "deciduous tree"},
                               {"use": "food", "note": "y", "quote": "edible fruit"}]}
        kept, dropped = extract.verify(facts, self.TEXT)
        self.assertEqual([u["use"] for u in kept["uses_real"]], ["timber"])
        self.assertEqual(dropped, ["uses_real:food"])


class Ids(unittest.TestCase):
    def test_species_id(self):
        self.assertEqual(species_id("Olea europaea subsp. europaea"), "olea_europaea_europaea")


if __name__ == "__main__":
    unittest.main()
