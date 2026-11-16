"""Offline tests: python3 -m unittest discover -s pipeline/tests   (run from the repo root)"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import assemble
import extract
import fetch
import photos
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


class NewFactTypes(unittest.TestCase):
    TEXT = "The tree grows 60-78 m tall. Its leaves are in opposite pairs. Bark is grey. Seeds germinate at 20 C."

    def test_numeric_measurement_needs_a_digit_in_its_quote(self):
        facts = {"measurements": [{"what": "height", "unit": "cm", "max": 7800, "quote": "The tree grows 60-78 m tall"},
                                  {"what": "spread", "unit": "cm", "max": 500, "quote": "Bark is grey"}]}   # real quote, but no number
        kept, dropped = extract.verify(facts, self.TEXT)
        self.assertEqual([m["what"] for m in kept["measurements"]], ["height"])
        self.assertEqual(dropped, ["measurements:spread"])

    def test_architecture_and_propagation_checked_per_item(self):
        facts = {"architecture": [{"aspect": "leaf_arrangement", "value": "opposite", "quote": "leaves are in opposite pairs"},
                                  {"aspect": "crown_shape", "value": "umbrella", "quote": "crown is umbrella shaped"}],
                 "propagation": [{"topic": "germination", "fact": "20 C", "quote": "Seeds germinate at 20 C"}]}
        kept, dropped = extract.verify(facts, self.TEXT)
        self.assertEqual(len(kept["architecture"]), 1)
        self.assertEqual(len(kept["propagation"]), 1)
        self.assertEqual(dropped, ["architecture:crown_shape"])


class SizeSection(unittest.TestCase):
    WP = {"found": True, "title": "Peach", "url": "https://en.wikipedia.org/wiki/Peach"}

    def test_placeholder_when_no_height(self):
        size = assemble.build_size({}, "bushy", self.WP)
        self.assertEqual(size["source"], "pending")

    def test_range_beats_single_value_and_rare_sets_common_max(self):
        meas = [{"what": "height", "unit": "cm", "min": 300, "max": 300, "qualifier": "typical", "quote": "q1 3 m"},
                {"what": "height", "unit": "cm", "max": 1000, "qualifier": "rare_maximum", "quote": "q2 10 m"},
                {"what": "spread", "unit": "cm", "min": 300, "max": 400, "qualifier": "range", "quote": "q3 3 to 4 m"},
                {"what": "trunk_diameter", "unit": "cm", "max": 20, "qualifier": "maximum", "quote": "q4 20 cm"}]
        size = assemble.build_size({"measurements": meas}, "tree", self.WP)
        self.assertEqual(size["height_cm"], {"min": 300, "max": 1000, "common_max": 300})
        self.assertEqual(size["spread_cm"], {"min": 300, "max": 400})
        self.assertEqual(size["trunk_diameter_cm"], {"max": 20})
        self.assertEqual(size["height_sources"][0]["name"], "Wikipedia: Peach")


class Photos(unittest.TestCase):
    def test_licences(self):
        for ok in ("CC BY-SA 4.0", "CC BY 3.0", "CC0", "Public domain"):
            self.assertTrue(photos.license_ok(ok), ok)
        for bad in ("CC BY-NC 4.0", "CC BY-ND 2.0", "", "Fair use", "All rights reserved"):
            self.assertFalse(photos.license_ok(bad), bad)

    def test_roles_from_title_and_category(self):
        self.assertEqual(photos.best_role(photos.tag_roles("Olive tree fruits ripe.jpg", "", [], set())), "fruit")
        self.assertEqual(photos.best_role(photos.tag_roles("IMG_1.jpg", "close-up of the flowers", [], set())), "flower")
        self.assertEqual(photos.best_role(photos.tag_roles("Bare twigs in winter.jpg", "", [], set())), "branches")
        self.assertEqual(photos.best_role(photos.tag_roles("IMG_2.jpg", "", [], set())), "habit")

    def test_select_filters_and_balances(self):
        def im(title, lic="CC BY 4.0", author="a", w=2000):
            return {"title": title, "mime": "image/jpeg", "license": lic, "author": author, "description": "", "categories": [],
                    "thumb": "u", "width": w, "height": w, "original": "o", "page": "p"}
        infos = {t: im(t) for t in ("File:Rose flower 1.jpg", "File:Rose flower 2.jpg")}
        infos["File:Rose flower nc.jpg"] = im("File:Rose flower nc.jpg", lic="CC BY-NC 4.0")
        infos["File:Rose herbarium sheet flower.jpg"] = im("File:Rose herbarium sheet flower.jpg")
        infos["File:Rose fruit.jpg"] = im("File:Rose fruit.jpg", author="b")
        chosen = photos.select(infos, {})
        titles = [c["title"] for c in chosen]
        self.assertNotIn("File:Rose flower nc.jpg", titles)
        self.assertNotIn("File:Rose herbarium sheet flower.jpg", titles)
        self.assertEqual(sorted(c["role"] for c in chosen), ["flower", "flower", "fruit"])


class Distribution(unittest.TestCase):
    def test_native_vs_introduced(self):
        wc = "The World Checklist of Vascular Plants (WCVP)"
        recs = [{"locality": "Morocco", "locationId": "TDWG:MOR", "source": wc},
                {"locality": "Azores", "locationId": "TDWG:AZO", "source": wc, "establishmentMeans": "INTRODUCED"},
                {"locality": "North America", "source": "Integrated Taxonomic Information System"}]
        old = fetch.get_json
        fetch.get_json = lambda url: {"results": recs, "endOfRecords": True}
        try:
            d = fetch.distribution(1)
        finally:
            fetch.get_json = old
        self.assertEqual([n["code"] for n in d["native"]], ["MOR"])
        self.assertEqual([n["code"] for n in d["introduced"]], ["AZO"])
        self.assertEqual(d["wcvp_records"], 2)


if __name__ == "__main__":
    unittest.main()
