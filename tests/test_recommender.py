import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

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


TODAY = date(2026, 10, 19)


def price(amount: float, checked: date = TODAY) -> dict:
    return {"amount": amount, "unit": "per_user", "billing": "annual",
            "checked_at": checked.isoformat(), "source_url": "https://example.com/pricing"}


class DecisionRules(unittest.TestCase):
    """Each rule, with the inputs that trigger it. Prices and claims are patched; purchases and facts are real."""

    def run_rec(self, vendor, plan, cur, memory, last_price_bullets=()):
        with mock.patch.object(R, "current_price", return_value=cur), \
             mock.patch.object(R, "load_bullets", return_value=list(last_price_bullets)):
            return R.recommend(vendor, plan, "x", memory=memory, today=TODAY)

    def test_must_have_met_by_verified_fact_renews(self):
        # Asana Enterprise has a verified SSO fact (eval/purchases/db.py), so the SSO must-have passes.
        out = self.run_rec("Asana", "Enterprise", price(25.0), {"must_have": ["SSO"], "max_price_per_seat": 30})
        self.assertEqual(out["recommendation"], "renew")
        sso = [c for c in out["evidence"]["memory_checks"] if "SSO" in c["rule"]][0]
        self.assertEqual(sso["result"], "pass")

    def test_must_have_missing_on_this_plan_means_review_alternatives(self):
        # The SSO fact is on Enterprise only, so Starter fails it.
        out = self.run_rec("Asana", "Starter", price(10.99), {"must_have": ["SSO"], "max_price_per_seat": 30})
        self.assertEqual(out["recommendation"], "review_alternatives")
        self.assertTrue(any("Verified on Enterprise only" in r for r in out["reasons"]))

    def test_price_up_past_tolerance_means_negotiate(self):
        # Last Asana Starter purchase was 10.99 (purchases.db). 12.50 is +13.7%, over the 10% tolerance.
        out = self.run_rec("Asana", "Starter", price(12.50), {"price_change_tolerance_pct": 10, "max_price_per_seat": 30})
        self.assertEqual(out["recommendation"], "negotiate")

    def test_price_within_tolerance_renews(self):
        out = self.run_rec("Asana", "Starter", price(11.00), {"price_change_tolerance_pct": 10, "max_price_per_seat": 30})
        self.assertEqual(out["recommendation"], "renew")

    def test_stale_price_lowers_freshness_and_says_so(self):
        old = price(11.00, checked=TODAY - timedelta(days=400))
        out = self.run_rec("Asana", "Starter", old, {"max_price_per_seat": 30})
        self.assertEqual(out["factors"]["freshness"], 0.8)
        self.assertTrue(any("Re-check before buying" in r for r in out["reasons"]))

    def test_no_price_never_renews(self):
        out = self.run_rec("Asana", "Enterprise", None, {"must_have": ["SSO"]})
        self.assertEqual(out["recommendation"], "insufficient_data")


if __name__ == "__main__":
    unittest.main()
