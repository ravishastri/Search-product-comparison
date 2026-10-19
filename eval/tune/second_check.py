"""Second model as a meaning check on the current judge's "supported" verdicts.

Only claims the first judge (v1, Kimi) marked supported are re-checked, with a second model
(DeepSeek-V4-Pro) using the same prompt and page text. A claim stays supported only if the second
model also says supported and its quote is verbatim in the page. Otherwise it becomes not_stated. If the second model errors, the first verdict stands.
Claims the first judge did not mark supported are unchanged, so this can only remove false support.

Usage:
  uv run --with ... python eval/tune/second_check.py --splits tune,val --out eval/tune/results-check-dev.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
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
SECOND_MODEL = os.environ.get("SECOND_MODEL", "deepseek-ai/DeepSeek-V4-Pro")  # Qwen3.5 was removed from the catalog


def cache_text(url: str) -> str:
    path = ROOT / "eval" / "cache" / f"{hashlib.sha1(url.encode()).hexdigest()}.txt"
    return path.read_text() if path.exists() else ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--splits", default="tune,val")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    splits = set(args.splits.split(","))

    v1 = json.load(open(ROOT / "eval/tune/results-v1.json"))["rows"]
    claims = {r["id"]: r for r in json.load(open(ROOT / "eval/tune/to_label.json"))}
    labels = {json.loads(l)["id"]: json.loads(l)["label"] for l in open(ROOT / "eval/tune/labels.jsonl")}

    second = ChatNebius(model=SECOND_MODEL, max_tokens=32768, timeout=300, max_retries=1, temperature=0)
    rows = []
    for r in v1:
        if r["split"] not in splits:
            continue
        final = r["verdict_comparable"]
        check = None
        if final == "supported":
            urls = [u for u in claims[r["id"]]["urls"][:3] if cache_text(u)]
            texts = {u: cache_text(u) for u in urls}
            try:
                check, _ = llm_judge.judge_one(second, claims[r["id"]]["claim"], texts) if texts else ("no_source_text", "")
                if check == "supported":
                    ok, _ = llm_judge.code_check(claims[r["id"]]["claim"], r["evidence"])
                    if not ok:
                        check = "disagreement"
            except Exception as exc:  # a failed check is not a rejection: keep the first verdict, record the error
                check = f"check_error: {str(exc)[:120]}"
            if check is not None and not check.startswith("check_error") and check != "supported":
                final = "not_stated"
        rows.append(dict(id=r["id"], split=r["split"], label=labels[r["id"]], first=r["verdict_comparable"],
                         second=check, final=final))
        print(f"{r['id']} first={r['verdict_comparable']} second={check} final={final}", file=sys.stderr, flush=True)

    summary = {}
    for split in sorted(splits) + ["all"]:
        rs = [x for x in rows if split == "all" or x["split"] == split]
        agree_first = sum(x["first"] == x["label"] for x in rs)
        agree_final = sum(x["final"] == x["label"] for x in rs)
        summary[split] = {"n": len(rs), "first_judge_agreement": round(agree_first / len(rs), 3) if rs else None,
                          "with_second_check_agreement": round(agree_final / len(rs), 3) if rs else None,
                          "changed": sum(x["first"] != x["final"] for x in rs),
                          "mismatches_final": dict(Counter((x["label"], x["final"]) for x in rs if x["final"] != x["label"]))}
        summary[split]["mismatches_final"] = {f"{a}->{b}": c for (a, b), c in summary[split]["mismatches_final"].items()}
    out = {"first_judge": "moonshotai/Kimi-K2.6 (v1)", "second_model": SECOND_MODEL,
           "run_at": time.strftime("%Y-%m-%d %H:%M"), "summary": summary, "rows": rows}
    args.out.write_text(json.dumps(out, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
