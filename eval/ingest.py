"""Ingest verified pricing claims from a run into the price store.

For each pricing claim the judge marked "supported":
  1. The model extracts plan, amount, currency, unit, billing period, and quotes the sentence it used.
  2. Code checks the quote appears in the cached page text and contains the amount.
  3. The fact goes through the store's gate. Failures go to the review queue, not the history.

Usage:
  uv run --with langchain-nebius python eval/ingest.py runs/linear-20261018-143031 \
      eval/results/evaluator-linear-llm.json --vendor Linear --checked 2026-10-19
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))

from judge import parse_claims  # noqa: E402
from store import Store  # noqa: E402

PROMPT = """Extract one price from the claim, using only the source text.
Return only JSON:
{"plan": "...", "amount": number, "currency": "USD", "unit": "per_user" | "per_agent" | "per_seat" | "per_million_tokens" | "flat" | null,
 "billing": "monthly" | "annual" | "usage" | "one_time" | null, "quote": "the exact sentence from the source text that states this price"}
Use null for unit or billing if the source does not say. Do not guess."""


def cache_text(url: str) -> str:
    path = ROOT / "eval" / "cache" / f"{hashlib.sha1(url.encode()).hexdigest()}.txt"
    return path.read_text() if path.exists() else ""


def norm(s: str) -> str:
    return " ".join(s.split())


def extract(llm, claim: str, page: str) -> dict:
    reply = llm.invoke([{"role": "system", "content": PROMPT},
                        {"role": "user", "content": f"Claim: {claim}\n\nSource text:\n{page[:20000]}"}]).content
    text = re.sub(r"<think>.*?</think>", "", reply, flags=re.S)
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0)) if m else {}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("judge_json", type=Path)
    ap.add_argument("--vendor", required=True)
    ap.add_argument("--checked", required=True, help="YYYY-MM-DD the page was checked")
    ap.add_argument("--db", default=str(ROOT / "eval" / "data" / "prices.db"))
    args = ap.parse_args()

    from langchain_nebius import ChatNebius
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    llm = ChatNebius(model="moonshotai/Kimi-K2.6", max_tokens=4096, timeout=180, temperature=0)

    run = json.loads((args.run_dir / "run.json").read_text())
    url_of = {s["id"]: s["url"] for s in run.get("sources", [])}
    verdicts = {r["text"]: r["verdict"] for r in json.loads(args.judge_json.read_text())["claims"]}
    store = Store(args.db)
    counts = {"stored": 0, "unchanged": 0, "changed": 0, "queued": 0, "skipped": 0}

    for claim in parse_claims((args.run_dir / "brief.md").read_text()):
        if claim["section"] != "Pricing and plans" or not re.search(r"\$\d", claim["text"]):
            continue
        if verdicts.get(claim["text"]) != "supported":
            counts["skipped"] += 1
            continue
        urls = [url_of[i] for i in claim["ids"] if i in url_of]
        page_url = next((u for u in urls if cache_text(u)), None)
        if not page_url:
            store.record_price(vendor=args.vendor, plan="unknown", amount=0, currency="", unit="", billing="",
                               source_url=urls[0] if urls else "", verdict="unverified", checked_at=args.checked)
            counts["queued"] += 1
            continue

        page = cache_text(page_url)
        fact = extract(llm, claim["text"], page)
        quote = norm(str(fact.get("quote", "")))
        quote_ok = bool(quote) and quote in norm(page)
        amount_ok = quote_ok and fact.get("amount") is not None and f"{fact['amount']:g}" in quote.replace(",", "")
        verdict = "supported" if (quote_ok and amount_ok) else "unverified"
        status = store.record_price(
            vendor=args.vendor, plan=str(fact.get("plan") or "unknown"), amount=float(fact.get("amount") or 0),
            currency=str(fact.get("currency") or ""), unit=str(fact.get("unit") or ""),
            billing=str(fact.get("billing") or ""), source_url=page_url, verdict=verdict,
            checked_at=args.checked, page_hash=hashlib.sha256(page.encode()).hexdigest()[:16])
        counts[status] = counts.get(status, 0) + 1
        print(f"{status:<9} {claim['text'][:90]}")

    print(json.dumps(counts))
    store.close()


if __name__ == "__main__":
    main()
