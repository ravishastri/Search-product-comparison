"""Deterministic judge for a run folder: checks each brief claim against its cited sources.

No model calls, so it runs without API keys. It catches citation errors, prices that do not
appear in the cited text, quotes that are not verbatim, and undated or stale sources.
It does not judge whether a claim is true in general; that is the LLM judge's job (see PROGRESS.md 4e).

Usage:
  python3 eval/judge.py runs/linear-20261018-113305 --ground-truth eval/golden/ground_truth.json --product Linear
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date, timedelta
from pathlib import Path

PRICE = re.compile(r"\$\d[\d,]*(?:\.\d+)?")
QUOTE = re.compile(r'"([^"]{8,})"')
CLAIM = re.compile(r"^- (?P<text>.+?)\s*(?P<cites>(?:\[S\d+\])+)(?P<notes>(?:\s*\([^)]*\))*)\s*$")
STALE_DAYS = 365


def parse_claims(brief: str) -> list[dict]:
    """Claims are bullets in the claim sections, before '## Unsupported claims' or '## Sources'."""
    claims, section = [], None
    for line in brief.splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
            continue
        if section in (None, "Unsupported claims", "Sources") or not line.startswith("- "):
            continue
        m = CLAIM.match(line)
        if not m:
            continue
        claims.append({
            "section": section,
            "text": m.group("text").strip(),
            "ids": re.findall(r"S\d+", m.group("cites")),
        })
    return claims


def check_run(run_dir: Path, ground_truth: dict | None, product: str | None, today: date) -> dict:
    run = json.loads((run_dir / "run.json").read_text())
    brief = (run_dir / "brief.md").read_text()
    sources = {s["id"]: s for s in run.get("sources", [])}
    claims = parse_claims(brief)
    cutoff = today - timedelta(days=STALE_DAYS)

    rows = []
    for c in claims:
        cited = [sources[i] for i in c["ids"] if i in sources]
        cited_text = " ".join(s.get("content", "") for s in cited)
        prices = PRICE.findall(c["text"])
        quotes = QUOTE.findall(c["text"])
        dates = [s.get("published") for s in cited if s.get("published")]
        rows.append({
            "section": c["section"],
            "text": c["text"][:120],
            "all_ids_valid": len(cited) == len(c["ids"]) and bool(cited),
            "prices": prices,
            "prices_in_cited_text": all(p in cited_text for p in prices) if prices else None,
            "quotes": len(quotes),
            "quotes_verbatim": all(q in cited_text for q in quotes) if quotes else None,
            "dated": bool(dates),
            "stale": any(d < cutoff.isoformat() for d in dates),
        })

    def rate(key: str) -> float | None:
        vals = [r[key] for r in rows if r[key] is not None]
        return round(sum(bool(v) for v in vals) / len(vals), 3) if vals else None

    summary = {
        "run": run_dir.name,
        "claims": len(rows),
        "cited_ids_valid": rate("all_ids_valid"),
        "price_claims": sum(1 for r in rows if r["prices"]),
        "prices_in_cited_text": rate("prices_in_cited_text"),
        "quoted_claims": sum(1 for r in rows if r["quotes"]),
        "quotes_verbatim": rate("quotes_verbatim"),
        "dated_claims": rate("dated"),
        "stale_claims": sum(1 for r in rows if r["stale"]),
        "errors": len(run.get("errors", [])),
    }

    if ground_truth and product and product in ground_truth.get("products", {}):
        facts = ground_truth["products"][product]["facts"]
        amounts = [f["price"] for f in facts]
        def in_brief(f: dict) -> bool:
            # "match" is a plain term (for example "free") for facts with no dollar amount.
            if "match" in f:
                return f["match"].lower() in brief.lower()
            return any(p in brief for p in PRICE.findall(f["price"]))

        found = [f for f in facts if in_brief(f)]
        summary["ground_truth_price_recall"] = round(len(found) / len(facts), 3) if facts else None
        summary["ground_truth_facts"] = len(facts)
        summary["ground_truth_found_in_brief"] = [f["price"] for f in found]
        summary["ground_truth_missing_from_brief"] = [f["price"] for f in facts if f not in found]

    return {"summary": summary, "claims": rows}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--ground-truth", type=Path)
    ap.add_argument("--product")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    gt = json.loads(args.ground_truth.read_text()) if args.ground_truth else None
    result = check_run(args.run_dir, gt, args.product, date.today())
    out = args.out or (Path("eval/results") / f"{args.run_dir.name}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))
    print(json.dumps(result["summary"], indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
