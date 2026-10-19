import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval" / "purchases"))
import recommender as R  # noqa: E402


class MemoryTests(unittest.TestCase):
    def test_parses_numbers_lists_and_text(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "m.md"
            p.write_text("# PM memory\n- max_price_per_seat: 12\n- must_have: SSO, time tracking\n"
                         "- price_change_tolerance_pct: 10\n- note: keep it simple\n")
            mem = R.load_memory(p)
        self.assertEqual(mem["max_price_per_seat"], 12.0)
        self.assertEqual(mem["must_have"], ["SSO", "time tracking"])
        self.assertEqual(mem["price_change_tolerance_pct"], 10.0)
        self.assertEqual(mem["note"], "keep it simple")


class ConfidenceTests(unittest.TestCase):
    def test_confidence_is_product_of_factors_and_clamped(self):
        out = R.finish("renew", [], {"a": 0.5, "b": 0.8}, 1.0, None, None, {}, [])
        self.assertEqual(out["confidence"], 0.4)
        out = R.finish("renew", [], {"a": 2.0}, 1.0, None, None, {}, [])
        self.assertEqual(out["confidence"], 1.0)


class RecommendationTests(unittest.TestCase):
    def test_no_verified_price_is_insufficient_data(self):
        out = R.recommend("NoSuchVendor", "Plan", "none", memory={}, today=date(2026, 10, 19))
        self.assertEqual(out["recommendation"], "insufficient_data")
        self.assertLess(out["confidence"], 0.5)

    def test_unmet_must_have_means_review_alternatives(self):
        out = R.recommend("YouTrack", "Per-user starting price", "youtrack",
                          memory={"must_have": ["SSO"]}, today=date(2026, 10, 19))
        self.assertEqual(out["recommendation"], "review_alternatives")

    def test_over_budget_means_review_alternatives(self):
        out = R.recommend("YouTrack", "Per-user starting price", "youtrack",
                          memory={"max_price_per_seat": 1.0}, today=date(2026, 10, 19))
        self.assertEqual(out["recommendation"], "review_alternatives")
        self.assertTrue(any("above the budget" in r for r in out["reasons"]))

    def test_illustrative_last_purchase_lowers_confidence(self):
        verified = R.recommend("YouTrack", "Per-user starting price", "youtrack", memory={}, today=date(2026, 10, 19))
        illustrative = R.recommend("Trello", "Premium", "trello", memory={}, today=date(2026, 10, 19))
        self.assertLess(illustrative["confidence"], verified["confidence"])


if __name__ == "__main__":
    unittest.main()
