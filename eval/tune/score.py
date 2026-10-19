"""Score the judge against the blind labels, by split.

Each labeled claim is judged with the current judge (eval/llm_judge.py: same prompt, cached page text,
verbatim-evidence check and the two-check rule). The judge verdict is then compared with the label.

Mapping for comparison: a verdict that the judge could not trust ("unverified_evidence", "disagreement")
counts as not_stated, since the claim is not shown as supported. The raw verdict is kept too.

Usage:
  uv run --with ... python eval/tune/score.py --out eval/tune/results-v1.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "eval"))

from dotenv import load_dotenv  # noqa: E402
from langchain_nebius import ChatNebius  # noqa: E402

import llm_judge  # noqa: E402

load_dotenv(ROOT / ".env")


def cache_text(url: str) -> str:
    path = ROOT / "eval" / "cache" / f"{hashlib.sha1(url.encode()).hexdigest()}.txt"
    return path.read_text() if path.exists() else ""


def load_items() -> list[dict]:
    rows = {r["id"]: r for r in json.load(open(ROOT / "eval/tune/to_label.json")) if not r.get("excluded")}
    labels = {}
    for line in open(ROOT / "eval/tune/labels.jsonl"):
        rec = json.loads(line)
        labels[rec["id"]] = rec["label"]
    return [dict(id=i, split=rows[i]["split"], claim=rows[i]["claim"], urls=rows[i]["urls"][:3], label=labels[i])
            for i in rows if i in labels]


def comparable(verdict: str) -> str:
    return "not_stated" if verdict in ("unverified_evidence", "disagreement", "judge_error") else verdict


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    items = load_items()
    llm = ChatNebius(model=llm_judge.JUDGE_MODEL, max_tokens=32768, timeout=300, max_retries=1, temperature=0)
    results = []
    for n, it in enumerate(items, 1):
        texts = {u: cache_text(u) for u in it["urls"] if cache_text(u)}
        if not texts:
            verdict, evidence = "no_source_text", ""
        else:
            try:
                verdict, evidence = llm_judge.judge_one(llm, it["claim"], texts)
                if verdict == "supported":
                    ok, reason = llm_judge.code_check(it["claim"], evidence)
                    if not ok:
                        verdict, evidence = "disagreement", f"{reason}. judge quote: {evidence}"[:300]
            except Exception as exc:  # keep going; the error is recorded
                verdict, evidence = "judge_error", str(exc)[:200]
        results.append(dict(id=it["id"], split=it["split"], label=it["label"], verdict=verdict,
                            verdict_comparable=comparable(verdict), evidence=evidence[:300]))
        print(f"[{n}/{len(items)}] {it['id']} label={it['label']} judge={verdict}", file=sys.stderr, flush=True)

    summary = {}
    for split in ("tune", "val", "test", "all"):
        rs = [r for r in results if split == "all" or r["split"] == split]
        agree = sum(r["verdict_comparable"] == r["label"] for r in rs)
        summary[split] = {"n": len(rs), "agreement": round(agree / len(rs), 3) if rs else None,
                          "confusion": dict(Counter((r["label"], r["verdict_comparable"]) for r in rs).most_common())}
        summary[split]["confusion"] = {f"{a}->{b}": c for (a, b), c in summary[split]["confusion"].items()}
    out = {"judge": llm_judge.JUDGE_MODEL, "max_chars_per_url": llm_judge.MAX_CHARS_PER_URL,
           "run_at": time.strftime("%Y-%m-%d %H:%M"), "summary": summary, "rows": results}
    args.out.write_text(json.dumps(out, indent=2))
    print(json.dumps({k: {"n": v["n"], "agreement": v["agreement"]} for k, v in summary.items()}, indent=2))


if __name__ == "__main__":
    main()
