import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.store import Store  # noqa: E402


def fact(**over):
    base = dict(vendor="Linear", plan="Basic", amount=10, currency="USD", unit="per_user",
                billing="annual", source_url="https://linear.app/pricing", verdict="supported",
                checked_at="2026-10-19")
    base.update(over)
    return base


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "prices.db")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_new_price_is_stored(self):
        self.assertEqual(self.store.record_price(**fact()), "new")
        self.assertEqual(len(self.store.current("Linear")), 1)

    def test_same_price_is_not_duplicated(self):
        self.store.record_price(**fact())
        self.assertEqual(self.store.record_price(**fact(checked_at="2026-10-26")), "unchanged")
        self.assertEqual(len(self.store.history("Linear")), 1)

    def test_changed_price_closes_old_row_and_raises_alert(self):
        self.store.record_price(**fact())
        self.assertEqual(self.store.record_price(**fact(amount=12, checked_at="2026-11-01")), "changed")
        rows = self.store.history("Linear")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["effective_to"], "2026-11-01")
        self.assertIsNone(rows[1]["effective_to"])
        alerts = self.store.open_alerts()
        self.assertEqual(len(alerts), 1)
        self.assertEqual((alerts[0]["old_amount"], alerts[0]["new_amount"]), (10, 12))

    def test_unsupported_verdict_goes_to_review_queue(self):
        self.assertEqual(self.store.record_price(**fact(verdict="not_stated")), "queued")
        self.assertEqual(self.store.history("Linear"), [])
        self.assertIn("not supported", self.store.review_queue()[0]["reason"])

    def test_missing_unit_goes_to_review_queue(self):
        self.assertEqual(self.store.record_price(**fact(unit="")), "queued")
        self.assertEqual(self.store.history("Linear"), [])

    def test_missing_billing_goes_to_review_queue(self):
        self.assertEqual(self.store.record_price(**fact(billing="sometimes")), "queued")

    def test_different_units_are_separate_series(self):
        self.store.record_price(**fact(unit="per_user"))
        self.store.record_price(**fact(unit="per_agent", amount=6))
        self.assertEqual(len(self.store.current("Linear")), 2)
        self.assertEqual(self.store.open_alerts(), [])


if __name__ == "__main__":
    unittest.main()
