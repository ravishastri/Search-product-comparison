"""Phase 4 driver: run the evaluator and the starter on each golden product, then judge both.

Each step is skipped when its output already exists, so a stopped run can be resumed.
Two lanes can run in parallel; each lane takes a list of product slugs.

Usage:
  uv run --with ... python eval/phase4.py lane-a
  uv run --with ... python eval/phase4.py lane-b
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# slug, product name, description, category (used by evaluator.py)
PRODUCTS = [
    ("linear", "Linear", "Issue tracker for software teams", "issuetracker"),
    ("jira", "Jira", "Issue tracking and project management for software teams", "issuetracker"),
    ("plane", "Plane", "Open-source project management for software teams", "issuetracker"),
    ("shortcut", "Shortcut", "Project management for software product and engineering teams", "issuetracker"),
    ("clickup", "ClickUp", "All-in-one project management and productivity app", "project management"),
    ("asana", "Asana", "Work management platform for teams", "project management"),
    ("trello", "Trello", "Visual kanban board for task and project tracking", "project management"),
    ("youtrack", "YouTrack", "Issue tracker from JetBrains for software teams", "issuetracker"),
]
LANES = {
    "lane-a": ["linear", "jira", "plane", "shortcut"],
    "lane-b": ["clickup", "asana", "trello", "youtrack"],
}


def question(name: str, desc: str) -> str:
    return (f"Compare {name}, {desc.lower()}, with its similar products. Cover pricing and plans, "
            "competitive landscape, and recent reception. Include source URLs for every claim.")


def run(cmd: list[str], log: Path | None = None) -> None:
    print("  $", " ".join(cmd)[:160], flush=True)
    if log is None:
        subprocess.run(cmd, cwd=ROOT, check=True)
        return
    with log.open("w") as fh:
        subprocess.run(cmd, cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT, check=True)


def newest_run(slug: str, name: str) -> Path:
    prefix = name.lower().replace(" ", "-") + "-"
    runs = sorted(p for p in (ROOT / "runs").iterdir() if p.is_dir() and p.name.startswith(prefix))
    return runs[-1]


def do(slug: str, name: str, desc: str, category: str) -> None:
    print(f"== {name}", flush=True)
    starter_out = ROOT / "eval/runs/starter" / f"{slug}.txt"
    claims = ROOT / "eval/runs/starter" / f"{slug}-claims.json"
    s_judge = ROOT / "eval/results" / f"starter-{slug}-llm.json"
    e_det = ROOT / "eval/results" / f"evaluator-{slug}-det.json"
    e_judge = ROOT / "eval/results" / f"evaluator-{slug}-llm.json"

    # 1. Evaluator run (skipped if a run for this product already exists from today).
    if not any((ROOT / "runs").glob(f"{name.lower().replace(' ', '-')}-2026*")):
        run(["uv", "run", "--with", "langchain-nebius>=0.1.0", "--with", "python-dotenv>=1.0.0",
             "--with", "tavily-python>=0.5.0", "--with", "rich>=13.0.0", "--with", "typer>=0.12.0",
             "--with", "langfuse>=5.0.0", "evaluator.py", "--product", name, "--description", desc,
             "--category", category])
    evaluator_run = newest_run(slug, name)

    # 2. Starter run.
    if not starter_out.exists():
        starter_out.parent.mkdir(parents=True, exist_ok=True)
        run(["uv", "run", "--with", "langchain-nebius>=0.1.0", "--with", "langchain-tavily>=0.2.0",
             "--with", "langchain>=1.0.0", "--with", "python-dotenv>=1.0.0", "--with", "rich>=13.0.0",
             "--with", "typer>=0.12.0", "starter_agent.py", question(name, desc)], log=starter_out)

    # 3. Claims from the starter's free text.
    if not claims.exists():
        run(["uv", "run", "--with", "langchain-nebius>=0.1.0", "--with", "python-dotenv>=1.0.0",
             "python", "eval/extract_claims.py", str(starter_out), str(claims)])

    # 4. Judge the starter, then the evaluator (LLM judge on full page text).
    if not s_judge.exists():
        run(["uv", "run", "--with", "langchain-nebius>=0.1.0", "--with", "python-dotenv>=1.0.0",
             "--with", "tavily-python>=0.5.0", "python", "eval/llm_judge.py", str(claims), str(s_judge)],
            log=s_judge.with_suffix(".log"))
    if not e_judge.exists():
        run(["uv", "run", "--with", "langchain-nebius>=0.1.0", "--with", "python-dotenv>=1.0.0",
             "--with", "tavily-python>=0.5.0", "python", "eval/llm_judge.py", str(evaluator_run), str(e_judge)],
            log=e_judge.with_suffix(".log"))

    # 5. Deterministic checks for the evaluator (no model calls).
    if not e_det.exists():
        run(["python3", "eval/judge.py", str(evaluator_run), "--ground-truth", "eval/golden/ground_truth.json",
             "--product", name, "--out", str(e_det)])
    print(f"   done {name}", flush=True)


def main() -> None:
    lane = sys.argv[1]
    wanted = set(LANES[lane])
    for slug, name, desc, category in PRODUCTS:
        if slug in wanted:
            try:
                do(slug, name, desc, category)
            except subprocess.CalledProcessError as exc:
                print(f"   FAILED {name}: step exited {exc.returncode}; continuing", flush=True)


if __name__ == "__main__":
    main()
