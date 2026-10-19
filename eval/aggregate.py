"""Aggregate Phase 4 results: starter vs evaluator per product, plus the evaluator's deterministic price check.

Reads the LLM judge summaries (starter-<slug>-llm.json, evaluator-<slug>-llm.json) and the
deterministic check (evaluator-<slug>-det.json). Writes eval/results/phase4-summary.json and prints a table.

Usage:
  python3 eval/aggregate.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "eval" / "results"
PRODUCTS = ["linear", "jira", "plane", "shortcut", "clickup", "asana", "trello", "youtrack"]


def load(path: Path) -> dict | None:
    return json.loads(path.read_text()) if path.exists() else None


def llm_summary(path: Path) -> dict | None:
    data = load(path)
    if not data:
        return None
    s = data["summary"]
    total = s["claims"] or 1
    return {
        "claims": s["claims"],
        "support_rate": s.get("support_rate"),
        "contradiction_rate": round(s["contradicted"] / total, 3),
        "not_stated_rate": round(s["not_stated"] / total, 3),
        "no_source_rate": round(s["no_source_text"] / total, 3),
        "supported": s["supported"],
        "contradicted": s["contradicted"],
    }


def main() -> None:
    rows = []
    for slug in PRODUCTS:
        starter_path = RESULTS / f"starter-{slug}-llm.json"
        evaluator_path = RESULTS / f"evaluator-{slug}-llm.json"
        det = load(RESULTS / f"evaluator-{slug}-det.json")
        rows.append({
            "product": slug,
            "starter": llm_summary(starter_path),
            "evaluator": llm_summary(evaluator_path),
            "evaluator_prices_in_cited_text": det["summary"].get("prices_in_cited_text") if det else None,
            "evaluator_ground_truth_recall": det["summary"].get("ground_truth_price_recall") if det else None,
        })

    totals = {}
    for side in ("starter", "evaluator"):
        rs = [r[side] for r in rows if r[side]]
        claims = sum(x["claims"] for x in rs)
        totals[side] = {
            "products": len(rs),
            "claims": claims,
            "support_rate": round(sum(x["supported"] for x in rs) / claims, 3) if claims else None,
            "contradiction_rate": round(sum(x["contradicted"] for x in rs) / claims, 3) if claims else None,
        }

    out = {"products": rows, "totals": totals}
    (RESULTS / "phase4-summary.json").write_text(json.dumps(out, indent=2))

    def cell(x, key):
        return "-" if not x or x.get(key) is None else (f"{x[key]:.0%}" if isinstance(x[key], float) else str(x[key]))

    print(f"{'product':<10} {'starter sup':>11} {'starter con':>11} {'eval sup':>9} {'eval con':>9} {'eval price ok':>13}")
    for r in rows:
        print(f"{r['product']:<10} {cell(r['starter'], 'support_rate'):>11} "
              f"{cell(r['starter'], 'contradiction_rate'):>11} {cell(r['evaluator'], 'support_rate'):>9} "
              f"{cell(r['evaluator'], 'contradiction_rate'):>9} {cell(r, 'evaluator_prices_in_cited_text'):>13}")
    print(f"\nwritten: {RESULTS / 'phase4-summary.json'}")


if __name__ == "__main__":
    main()
