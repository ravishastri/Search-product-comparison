"""Split a free-text answer into atomic claims, each with the URLs the answer cites for it.

Used for systems whose output is not the brief format (for example the starter agent).
The answer is the text after the last tool-call line, starting at the first markdown heading.

Usage:
  uv run eval/extract_claims.py eval/runs/starter/linear.txt eval/runs/starter/claims.json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_nebius import ChatNebius

load_dotenv()

PROMPT = """Split the answer below into atomic factual claims.
Rules:
- One fact per claim. Keep numbers, names, and dates exactly as written.
- Skip opinions, recommendations ("Choose X if..."), verdicts, and questions.
- For each claim, list the URLs the answer cites for it, copied exactly. Use [] if it cites none.
Return only JSON: {"claims": [{"text": "...", "urls": ["https://..."]}]}"""


def answer_text(raw: str) -> str:
    """Return the final answer: everything from the first markdown heading after the last tool call."""
    lines = raw.splitlines()
    last_tool = max((i for i, l in enumerate(lines) if l.startswith("Tool call")), default=-1)
    for i in range(last_tool + 1, len(lines)):
        if re.match(r"#{1,3} \S", lines[i]):
            return "\n".join(lines[i:])
    return "\n".join(lines[last_tool + 1:])


def parse_json(text: str) -> dict:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON object in model reply")
    return json.loads(m.group(0))


def main(src: str, out: str) -> None:
    answer = answer_text(Path(src).read_text())
    Path(out).with_name(f"{Path(out).stem}.answer.md").write_text(answer)  # kept so the input can be checked
    llm = ChatNebius(model="moonshotai/Kimi-K2.6", max_tokens=32768)
    reply = llm.invoke([{"role": "system", "content": PROMPT}, {"role": "user", "content": answer}]).content
    claims = [c for c in parse_json(reply).get("claims", []) if c.get("text")]
    Path(out).write_text(json.dumps({"claims": claims}, indent=2))
    print(f"{len(claims)} claims -> {out}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
