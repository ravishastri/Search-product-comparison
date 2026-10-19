"""Past purchases database (SQLite) for the buy recommender.

Each purchase records what the organization paid, for which plan and unit, on which date, and where
the price came from. A purchase whose price was not checked against a source is marked illustrative.

Usage:
  python3 eval/purchases/db.py --init --seed
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "eval" / "purchases" / "purchases.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS purchases (
    id INTEGER PRIMARY KEY,
    vendor TEXT NOT NULL,
    plan TEXT NOT NULL,
    unit TEXT NOT NULL,
    billing TEXT NOT NULL,
    unit_price REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    seats INTEGER NOT NULL,
    purchased_on TEXT NOT NULL,
    price_source TEXT,
    price_verified INTEGER NOT NULL DEFAULT 0,
    note TEXT
);
"""

# Random sample purchases. Only rows with price_verified=1 have a price confirmed on a source page.
SEED = [
    # verified: the price before the Oct 2025 increase is stated on the page
    dict(vendor="Jira", plan="Standard", unit="per_user", billing="annual", unit_price=7.75, seats=40,
         purchased_on="2025-06-02", price_verified=1,
         price_source="https://www.softwarepricingguide.com/atlassian-jira-pricing-2025-every-plan-the-data-center-vs-cloud-cost-decision-and-the-price-increases-nobody-warned-you-about",
         note="Standard was $7.75 before the October 2025 increase (page states 'Previously $7.75')."),
    # verified: earlier Plus price stated on the page (March 2026 pricing data)
    dict(vendor="Linear", plan="Plus", unit="per_user", billing="monthly", unit_price=14, seats=15,
         purchased_on="2025-03-10", price_verified=1,
         price_source="https://tech-insider.org/linear-vs-jira-2026",
         note="Plus was $14 before the increase to $16 (page: 'up from the $8 and $14 price points')."),
    # illustrative: not yet checked against a source for that date
    dict(vendor="Trello", plan="Premium", unit="per_user", billing="annual", unit_price=10, seats=60,
         purchased_on="2024-09-01", price_verified=1, price_source="https://web.archive.org/web/20240830141615/https://trello.com/pricing",
         note="Verified: Wayback snapshot 2024-08-30 lists Premium at $10 per user/month billed annually ($12.50 monthly)."),
    dict(vendor="Asana", plan="Starter", unit="per_user", billing="annual", unit_price=10.99, seats=25,
         purchased_on="2025-01-15", price_verified=1, price_source="https://web.archive.org/web/20250114204912/https://asana.com/pricing",
         note="Verified: Wayback snapshot 2025-01-14 lists Starter at $10.99 per user/month billed annually ($13.49 monthly)."),
    dict(vendor="ClickUp", plan="Business", unit="per_user", billing="annual", unit_price=12, seats=30,
         purchased_on="2024-11-01", price_verified=0, price_source=None,
         note="Illustrative. 2024 price not yet checked against a source."),
    dict(vendor="YouTrack", plan="Per-user starting price", unit="per_user", billing="monthly", unit_price=5.40, seats=20,
         purchased_on="2025-10-01", price_verified=1,
         price_source="https://sales.jetbrains.com/hc/en-gb/articles/28382668077970-%D0%A1hanges-to-YouTrack-Cloud-per-user-subscription-prices",
         note="Monthly rate from 1 October 2025 (JetBrains: USD 5.40 per user/month for 11+ users)."),
]


FACTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS verified_facts (
    id INTEGER PRIMARY KEY,
    vendor TEXT NOT NULL,
    plan TEXT NOT NULL,
    feature TEXT NOT NULL,
    included INTEGER NOT NULL,
    via_add_on TEXT,
    quote TEXT NOT NULL,
    source_url TEXT NOT NULL,
    checked_on TEXT NOT NULL
);
"""

# Facts checked against a source page. Each has the quote the check relied on.
FACTS = [
    dict(vendor="Trello", plan="Enterprise", feature="SSO", included=1,
         via_add_on="Atlassian Guard (separate subscription, from $4/month per user)",
         quote="Free SSO and user provisioning with Atlassian Guard",
         source_url="https://trello.com/pricing", checked_on="2026-10-19"),
]


def connect(path: Path = DB) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    db.executescript(FACTS_SCHEMA)
    return db


def seed_facts(db: sqlite3.Connection) -> int:
    added = 0
    for f in FACTS:
        exists = db.execute("SELECT 1 FROM verified_facts WHERE vendor=? AND plan=? AND feature=?",
                            (f["vendor"], f["plan"], f["feature"])).fetchone()
        if exists:
            continue
        db.execute("INSERT INTO verified_facts (vendor, plan, feature, included, via_add_on, quote, source_url, checked_on)"
                   " VALUES (:vendor, :plan, :feature, :included, :via_add_on, :quote, :source_url, :checked_on)", f)
        added += 1
    db.commit()
    return added


def facts_for(db: sqlite3.Connection, vendor: str, plan: str) -> list[dict]:
    return [dict(r) for r in db.execute(
        "SELECT * FROM verified_facts WHERE lower(vendor)=lower(?) AND lower(plan)=lower(?) AND included=1",
        (vendor, plan))]


def seed(db: sqlite3.Connection) -> int:
    if db.execute("SELECT COUNT(*) FROM purchases").fetchone()[0]:
        return 0
    for row in SEED:
        db.execute(
            "INSERT INTO purchases (vendor, plan, unit, billing, unit_price, seats, purchased_on, price_source,"
            " price_verified, note) VALUES (:vendor, :plan, :unit, :billing, :unit_price, :seats, :purchased_on,"
            " :price_source, :price_verified, :note)", row)
    db.commit()
    return len(SEED)


def purchases_for(db: sqlite3.Connection, vendor: str) -> list[dict]:
    return [dict(r) for r in db.execute(
        "SELECT * FROM purchases WHERE lower(vendor)=lower(?) ORDER BY purchased_on DESC", (vendor,))]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--seed", action="store_true")
    args = ap.parse_args()
    db = connect()
    if args.init or args.seed:
        print("seeded", seed(db) if args.seed else 0, "rows")
    print("purchases:", db.execute("SELECT COUNT(*) FROM purchases").fetchone()[0])


if __name__ == "__main__":
    main()
