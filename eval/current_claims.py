"""Write the claims from the latest run of each product, in the format the recommender reads.

Usage: python3 eval/current_claims.py
Output: eval/results/current/<slug>.json, one file per product.
Verdicts come from each run's judge: supported, not_stated, contradicted, no_source_text, or judge_error.
Quotes come from run.json "judge_evidence" when the run saved them (runs from 2026-10-19 onward).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRODUCTS = ["linear", "jira", "plane", "shortcut", "clickup", "asana", "trello", "youtrack"]
JUDGE_TAG = re.compile(r"\(judge: ([a-z_]+)\)$")


def latest_run(slug: str) -> Path | None:
    runs = sorted((ROOT / "runs").glob(f"{slug}-2026*/run.json"))
    return runs[-1] if runs else None


def claims_for(run: dict) -> list[dict]:
    evidence = run.get("judge_evidence", {})
    out = []
    for c in run.get("supported_claims", []):
        text = c["text"]
        verdict = "supported"
        if text.endswith("(source text unavailable, not judged)"):
            verdict = "no_source_text"
        elif text.endswith("(judge error, not judged)"):
            verdict = "judge_error"
        elif text.endswith("(price check unavailable)"):
            verdict = "supported"
        out.append({"text": text, "verdict": verdict, "evidence": evidence.get(text, "")})
    for c in run.get("unsupported_claims", []):
        text = c["text"]
        m = JUDGE_TAG.search(text)
        verdict = m.group(1) if m else "unsupported"
        out.append({"text": text, "verdict": verdict, "evidence": evidence.get(text, "")})
    return out


def main() -> None:
    out_dir = ROOT / "eval" / "results" / "current"
    out_dir.mkdir(parents=True, exist_ok=True)
    for slug in PRODUCTS:
        path = latest_run(slug)
        if path is None:
            print(f"{slug}: no run found")
            continue
        run = json.loads(path.read_text())
        claims = claims_for(run)
        (out_dir / f"{slug}.json").write_text(json.dumps({"run": path.parent.name, "claims": claims}, indent=2))
        print(f"{slug}: {path.parent.name}, {len(claims)} claims")


if __name__ == "__main__":
    main()
