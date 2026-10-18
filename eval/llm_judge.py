"""LLM judge: checks each claim against the full text of the URLs it cites.

Verdicts per claim:
  supported          the source states the claim, and the quoted evidence is verbatim in the source
  contradicted       the source states something different, with verbatim evidence
  not_stated         the source does not say
  unverified_evidence  the judge gave a verdict but its quote is not in the source (not trusted)
  no_source_text     none of the cited URLs could be fetched

Input is either a claims JSON file (from extract_claims.py) or an evaluator run folder
(claims come from brief.md, and source IDs are mapped to URLs through run.json).

Usage:
  uv run eval/llm_judge.py eval/runs/starter/claims.json eval/results/starter.json
  uv run eval/llm_judge.py runs/linear-20261018-143031 eval/results/linear-143031-llm.json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_nebius import ChatNebius

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_sources import fetch  # noqa: E402
from judge import parse_claims  # noqa: E402

load_dotenv()

PROMPT = """You check one claim against source text. Use only the source text provided.
Answer:
- "supported" if the source states the claim, with the same numbers, names, and dates.
- "contradicted" if the source states something different.
- "not_stated" if the source does not say.
Quote the single sentence from the source that decides your answer, copied character for character.
Return only JSON: {"verdict": "supported" | "contradicted" | "not_stated", "evidence": "..."}"""

MAX_CHARS_PER_URL = 20000
MAX_URLS_PER_CLAIM = 3


def norm(s: str) -> str:
    return " ".join(s.split())


def parse_json(text: str) -> dict:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON object in model reply")
    return json.loads(m.group(0))


def load_claims(path: Path) -> list[dict]:
    """Return [{text, urls}] from a claims file, or from an evaluator run folder."""
    if path.is_dir():
        run = json.loads((path / "run.json").read_text())
        url_of = {s["id"]: s["url"] for s in run.get("sources", [])}
        claims = parse_claims((path / "brief.md").read_text())
        return [{"text": c["text"], "urls": [url_of[i] for i in c["ids"] if i in url_of]} for c in claims]
    return json.loads(path.read_text())["claims"]


def judge_one(llm: ChatNebius, claim: str, texts: dict[str, str]) -> tuple[str, str]:
    source = "\n\n".join(f"[{u}]\n{t[:MAX_CHARS_PER_URL]}" for u, t in texts.items())
    reply = llm.invoke([
        {"role": "system", "content": PROMPT},
        {"role": "user", "content": f"Claim: {claim}\n\nSource text:\n{source}"},
    ]).content
    data = parse_json(reply)
    verdict = str(data.get("verdict", "not_stated"))
    evidence = str(data.get("evidence", ""))
    if verdict in ("supported", "contradicted"):
        trusted = bool(norm(evidence)) and any(norm(evidence) in norm(t) for t in texts.values())
        if not trusted:
            verdict = "unverified_evidence"
    return verdict, evidence


def main(src: str, out: str) -> None:
    claims = load_claims(Path(src))
    all_urls = [u for c in claims for u in c["urls"][:MAX_URLS_PER_CLAIM]]
    pages = fetch(all_urls)
    # Per-call timeout so one slow reply cannot stall the whole run.
    llm = ChatNebius(model="moonshotai/Kimi-K2.6", max_tokens=32768, timeout=120, max_retries=1)

    rows = []
    for n, c in enumerate(claims, 1):
        urls = c["urls"][:MAX_URLS_PER_CLAIM]
        texts = {u: pages[u] for u in urls if pages.get(u)}
        if not texts:
            rows.append({"text": c["text"], "verdict": "no_source_text", "evidence": ""})
        else:
            try:
                verdict, evidence = judge_one(llm, c["text"], texts)
            except Exception as exc:  # record the failure and keep going
                verdict, evidence = "judge_error", str(exc)[:200]
            rows.append({"text": c["text"], "verdict": verdict, "evidence": evidence[:300]})
        print(f"[{n}/{len(claims)}] {rows[-1]['verdict']}: {c['text'][:70]}", file=sys.stderr, flush=True)

    total = len(rows)
    count = lambda v: sum(r["verdict"] == v for r in rows)  # noqa: E731
    summary = {
        "claims": total,
        **{v: count(v) for v in ("supported", "contradicted", "not_stated", "unverified_evidence", "no_source_text")},
        "support_rate": round(count("supported") / total, 3) if total else None,
        "contradiction_rate": round(count("contradicted") / total, 3) if total else None,
    }
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps({"summary": summary, "claims": rows}, indent=2))
    print(json.dumps(summary, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
