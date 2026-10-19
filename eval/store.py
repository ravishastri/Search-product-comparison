"""Price history store: append-only verified prices, change alerts, and a review queue.

Rules:
- A price is stored only if its verdict is "supported" and it has a unit and billing period.
  Anything else goes to the review queue, not the history.
- A price that changes closes the current row (effective_to) and opens a new one, and an alert is raised.
- Rows are never edited or deleted, so the history can be audited.

Usage (from Python):
  from eval.store import Store
  s = Store("eval/data/prices.db")
  s.record_price(vendor="Linear", plan="Basic", amount=10, currency="USD", unit="per_user",
                 billing="annual", source_url="https://linear.app/pricing", verdict="supported",
                 checked_at="2026-10-19", page_hash="...")
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

UNITS = {"per_user", "per_agent", "per_seat", "per_million_tokens", "flat"}
BILLINGS = {"monthly", "annual", "usage", "one_time"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS price_facts (
    id INTEGER PRIMARY KEY,
    vendor TEXT NOT NULL,
    plan TEXT NOT NULL,
    amount REAL NOT NULL,
    currency TEXT NOT NULL,
    unit TEXT NOT NULL,
    billing TEXT NOT NULL,
    source_url TEXT NOT NULL,
    page_hash TEXT,
    checked_at TEXT NOT NULL,
    effective_from TEXT NOT NULL,
    effective_to TEXT
);
CREATE INDEX IF NOT EXISTS idx_current ON price_facts (vendor, plan, unit, billing, effective_to);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY,
    vendor TEXT NOT NULL,
    plan TEXT NOT NULL,
    unit TEXT NOT NULL,
    billing TEXT NOT NULL,
    old_amount REAL,
    new_amount REAL NOT NULL,
    currency TEXT NOT NULL,
    source_url TEXT NOT NULL,
    raised_at TEXT NOT NULL,
    acknowledged INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS review_queue (
    id INTEGER PRIMARY KEY,
    vendor TEXT,
    plan TEXT,
    amount REAL,
    currency TEXT,
    unit TEXT,
    billing TEXT,
    source_url TEXT,
    verdict TEXT,
    reason TEXT NOT NULL,
    queued_at TEXT NOT NULL
);
"""


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def close(self) -> None:
        self.db.close()

    def record_price(self, *, vendor: str, plan: str, amount: float, currency: str, unit: str,
                     billing: str, source_url: str, verdict: str, checked_at: str,
                     page_hash: str | None = None) -> str:
        """Store a verified price. Returns "unchanged", "new", "changed", or "queued"."""
        reason = self._gate_reason(amount, currency, unit, billing, source_url, verdict)
        if reason:
            self.db.execute(
                "INSERT INTO review_queue (vendor, plan, amount, currency, unit, billing, source_url, verdict, reason, queued_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (vendor, plan, amount, currency, unit, billing, source_url, verdict, reason, checked_at))
            self.db.commit()
            return "queued"

        current = self.db.execute(
            "SELECT * FROM price_facts WHERE vendor=? AND plan=? AND unit=? AND billing=? AND effective_to IS NULL",
            (vendor, plan, unit, billing)).fetchone()
        if current and abs(current["amount"] - amount) < 1e-9 and current["currency"] == currency:
            return "unchanged"

        if current:
            self.db.execute("UPDATE price_facts SET effective_to=? WHERE id=?", (checked_at, current["id"]))
            self.db.execute(
                "INSERT INTO alerts (vendor, plan, unit, billing, old_amount, new_amount, currency, source_url, raised_at)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (vendor, plan, unit, billing, current["amount"], amount, currency, source_url, checked_at))
            status = "changed"
        else:
            status = "new"

        self.db.execute(
            "INSERT INTO price_facts (vendor, plan, amount, currency, unit, billing, source_url, page_hash,"
            " checked_at, effective_from, effective_to) VALUES (?,?,?,?,?,?,?,?,?,?,NULL)",
            (vendor, plan, amount, currency, unit, billing, source_url, page_hash, checked_at, checked_at))
        self.db.commit()
        return status

    @staticmethod
    def _gate_reason(amount, currency, unit, billing, source_url, verdict) -> str | None:
        if verdict != "supported":
            return f"verdict is {verdict}, not supported"
        if unit not in UNITS:
            return f"unit missing or unknown: {unit!r}"
        if billing not in BILLINGS:
            return f"billing period missing or unknown: {billing!r}"
        if not currency:
            return "currency missing"
        if not source_url:
            return "source URL missing"
        if amount is None or amount <= 0:
            return f"amount not positive: {amount!r}"
        return None

    def history(self, vendor: str, plan: str | None = None) -> list[dict]:
        sql = "SELECT * FROM price_facts WHERE vendor=?"
        args: list = [vendor]
        if plan:
            sql += " AND plan=?"
            args.append(plan)
        sql += " ORDER BY plan, unit, billing, effective_from"
        return [dict(r) for r in self.db.execute(sql, args)]

    def current(self, vendor: str) -> list[dict]:
        return [dict(r) for r in self.db.execute(
            "SELECT * FROM price_facts WHERE vendor=? AND effective_to IS NULL ORDER BY plan, unit, billing", (vendor,))]

    def open_alerts(self) -> list[dict]:
        return [dict(r) for r in self.db.execute("SELECT * FROM alerts WHERE acknowledged=0 ORDER BY raised_at")]

    def review_queue(self) -> list[dict]:
        return [dict(r) for r in self.db.execute("SELECT * FROM review_queue ORDER BY queued_at")]
