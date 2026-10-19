"""Buy recommender: compares the current price and evidence with past purchases and the PM's memory.

Inputs:
  vendor, plan    what the organization buys or considers renewing
  memory          eval/purchases/pm_memory.md (editable)
  purchases       eval/purchases/purchases.db (past purchases)
  current price   eval/data/prices.db (verified prices only; rows exist only if they passed the gate)
  bullets         the judged claims for the product (eval/results/evaluator-<slug>-llm.json)

Output: a recommendation, a confidence score in [0, 1], the reasons, and each confidence factor.
Everything is rule-based, so each number can be traced.

Usage:
  uv run python eval/purchases/recommender.py --vendor Linear --plan Basic --slug linear
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "eval" / "purchases"))
sys.path.insert(0, str(ROOT / "eval"))

import db as purchases_db  # noqa: E402
from store import Store  # noqa: E402

MEMORY = ROOT / "eval" / "purchases" / "pm_memory.md"
PRICES = ROOT / "eval" / "data" / "prices.db"
STALE_DAYS = 90


def load_memory(path: Path = MEMORY) -> dict:
    """Parse `key: value` lines. Numbers become floats; comma lists become lists."""
    mem: dict = {}
    for line in path.read_text().splitlines():
        m = re.match(r"^- ([a-z_]+): (.+)$", line.strip())
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip()
        if re.fullmatch(r"[-\d.]+", value):
            mem[key] = float(value)
        elif key == "must_have":
            mem[key] = [v.strip() for v in value.split(",") if v.strip()]
        else:
            mem[key] = value
    return mem


def load_bullets(slug: str) -> list[dict]:
    path = ROOT / "eval" / "results" / f"evaluator-{slug}-llm.json"
    if not path.exists():
        return []
    return [{"text": c["text"], "verdict": c["verdict"], "evidence": c.get("evidence", "")}
            for c in json.loads(path.read_text())["claims"]]


def current_price(vendor: str, plan: str) -> dict | None:
    store = Store(PRICES)
    try:
        rows = [r for r in store.current(vendor) if plan.lower() in r["plan"].lower()]
    finally:
        store.close()
    return rows[0] if rows else None


def recommend(vendor: str, plan: str, slug: str, memory: dict | None = None, today: date | None = None) -> dict:
    memory = memory if memory is not None else load_memory()
    today = today or date.today()
    db = purchases_db.connect()
    past = [p for p in purchases_db.purchases_for(db, vendor) if plan.lower() in p["plan"].lower()]
    db.close()
    last = past[0] if past else None
    cur = current_price(vendor, plan)
    fdb = purchases_db.connect()
    facts = purchases_db.facts_for(fdb, vendor, plan)
    fdb.close()
    bullets = load_bullets(slug)
    supported = [b for b in bullets if b["verdict"] == "supported"]
    support_rate = len(supported) / len(bullets) if bullets else 0.0

    reasons: list[str] = []
    factors: dict[str, float] = {}
    confidence = 1.0

    # 1. Is there a verified current price?
    if cur is None:
        factors["current_price"] = 0.3
        reasons.append("No verified current price for this plan. Only verified prices are stored.")
        return finish("insufficient_data", reasons, factors, confidence, last, cur, memory, bullets, facts)
    factors["current_price"] = 1.0

    # 2. Compare with the last purchase.
    if last is None:
        factors["last_purchase"] = 0.7
        reasons.append("No past purchase for this plan, so no price change can be measured.")
        change = None
    else:
        factors["last_purchase"] = 1.0 if last["price_verified"] else 0.6
        if not last["price_verified"]:
            reasons.append(f"Last purchase price ({last['unit_price']}) is illustrative, not verified. "
                           "Confidence is reduced.")
        change = (cur["amount"] - last["unit_price"]) / last["unit_price"] * 100

    # 3. Evidence behind the current bullets.
    factors["evidence"] = round(0.5 + 0.5 * support_rate, 2)
    reasons.append(f"{len(supported)} of {len(bullets)} judged claims are supported by their cited pages.")

    # 4. Freshness of the current price.
    age = (today - date.fromisoformat(str(cur["checked_at"])[:10])).days
    factors["freshness"] = 0.8 if age > STALE_DAYS else 1.0
    if age > STALE_DAYS:
        reasons.append(f"Current price was checked {age} days ago. Re-check before buying.")

    # 5. Memory: budget and must-have features.
    budget_ok = True
    max_price = memory.get("max_price_per_seat")
    if max_price is not None and cur["amount"] > max_price:
        budget_ok = False
        reasons.append(f"Current price {cur['amount']} is above the budget of {max_price} per seat.")
    must = memory.get("must_have", [])
    missing = [m for m in must
               if not any(m.lower() in b["text"].lower() for b in supported)
               and not any(m.lower() == f["feature"].lower() for f in facts)]
    for m in missing:
        edb = purchases_db.connect()
        elsewhere = [f["plan"] for f in purchases_db.facts_elsewhere(edb, vendor, m) if f["plan"].lower() != plan.lower()]
        edb.close()
        where = f" Verified on {', '.join(sorted(set(elsewhere)))} only." if elsewhere else ""
        reasons.append(f"Must-have '{m}' is not in any supported claim for {plan}.{where}")
    memory_penalty = 0.0
    if not budget_ok:
        memory_penalty += 0.2
    memory_penalty += 0.15 * len(missing)
    factors["memory_fit"] = round(max(0.0, 1.0 - memory_penalty), 2)

    # Recommendation.
    tolerance = memory.get("price_change_tolerance_pct", 10.0)
    if not budget_ok or missing:
        rec = "review_alternatives"
    elif change is not None and change > tolerance:
        rec = "negotiate"
        reasons.append(f"Price is up {change:.1f}% from the last purchase, above the {tolerance:.0f}% tolerance.")
    else:
        rec = "renew"
        if change is not None:
            reasons.append(f"Price change since the last purchase: {change:+.1f}%, within the tolerance.")

    return finish(rec, reasons, factors, confidence, last, cur, memory, bullets, facts)


def build_evidence(last, cur, memory, bullets, facts=()) -> dict:
    """The evidence behind the recommendation: sources, memory checks, and the supported claims used."""
    supported = [b for b in bullets if b["verdict"] == "supported"]
    checks = []
    max_price = memory.get("max_price_per_seat")
    if max_price is not None and cur is not None:
        ok = cur["amount"] <= max_price
        checks.append({"rule": f"max_price_per_seat = {max_price:g}", "result": "pass" if ok else "fail",
                       "evidence": f"current verified price {cur['amount']:g} {cur['unit']} (source: {cur.get('source_url')})"})
    for m in memory.get("must_have", []):
        hit = next((b for b in supported if m.lower() in b["text"].lower()), None)
        fact = next((f for f in facts if m.lower() == f["feature"].lower()), None)
        if hit:
            ev = f"{hit['text']} | page says: \"{hit.get('evidence', '')[:160]}\""
        elif fact:
            ev = (f"verified: {fact['feature']} in {fact['plan']} via {fact['via_add_on'] or 'plan'} | "
                  f"page says: \"{fact['quote']}\" ({fact['source_url']})")
        else:
            ev = "no supported claim or verified fact for this plan"
        checks.append({"rule": f"must_have: {m}", "result": "pass" if (hit or fact) else "fail", "evidence": ev})
    terms = [m.lower() for m in memory.get("must_have", [])] + ["$", "per user", "per seat", "per month", "annual", "monthly"]
    used = [b for b in supported if any(t in b["text"].lower() for t in terms)][:6]
    return {
        "current_price": cur and {"amount": cur["amount"], "unit": cur["unit"], "billing": cur["billing"],
                                  "source_url": cur.get("source_url"), "checked_at": str(cur["checked_at"])[:10]},
        "last_purchase": last and {"unit_price": last["unit_price"], "purchased_on": last["purchased_on"],
                                   "price_verified": bool(last["price_verified"]), "price_source": last.get("price_source"),
                                   "note": last.get("note")},
        "memory_checks": checks,
        "supporting_claims": [{"text": b["text"], "quote": b.get("evidence", "")[:200]} for b in used],
    }


def finish(rec, reasons, factors, confidence, last, cur, memory, bullets, facts=()) -> dict:
    value = 1.0
    for f in factors.values():
        value *= f
    confidence = round(max(0.0, min(1.0, value)), 2)
    return {
        "evidence": build_evidence(last, cur, memory, bullets, facts),
        "recommendation": rec,
        "confidence": confidence,
        "reasons": reasons,
        "factors": factors,
        "last_purchase": last and {k: last[k] for k in ("plan", "unit_price", "purchased_on", "price_verified")},
        "current_price": cur and {"amount": cur["amount"], "unit": cur["unit"], "checked_at": cur["checked_at"]},
        "memory_used": memory,
        "bullets_checked": len(bullets),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vendor", required=True)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--slug", required=True, help="product slug for the judged bullets, e.g. linear")
    args = ap.parse_args()
    out = recommend(args.vendor, args.plan, args.slug)
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
