import importlib.util
import sys
import unittest
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
SCRIPT = BACKEND / "scripts" / "setup_restaurant_db.py"
SPEC = importlib.util.spec_from_file_location("setup_restaurant_db", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class RestaurantSeedValidationTests(unittest.TestCase):
    def test_committed_seed_files_are_consistent(self):
        counts = MODULE.validate_seed_files()
        self.assertEqual(counts["restaurant_ko"], 1000)
        self.assertEqual(counts["restaurant_en"], 1000)
        self.assertEqual(counts["restaurant_menu_ko"], 10003)
        self.assertEqual(counts["restaurant_menu_en"], 9697)
        self.assertEqual(counts["restaurant_review_ko"], 14996)
        self.assertEqual(counts["restaurant_review_en"], 9745)

    def test_loup_blanc_coordinates_match_yongsan_address(self):
        for language in ("ko", "en"):
            _, rows = MODULE._read_csv(
                MODULE.SEED_DIR / f"restaurant_{language}.csv"
            )
            row = next(item for item in rows if item["id"] == "6538765")
            self.assertAlmostEqual(float(row["lat"]), 37.52607542255891)
            self.assertAlmostEqual(float(row["lng"]), 126.963202539848)

    def test_vector_literal_is_pgvector_compatible(self):
        self.assertEqual(MODULE._vector_literal([0.5, -0.25]), "[0.5,-0.25]")


if __name__ == "__main__":
    unittest.main()
