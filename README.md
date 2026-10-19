# Search product comparison

A PM-tools evaluator and purchase recommender. It checks each price and SSO claim against the page it cites, judges the claims with an LLM, and recommends a recommended product, a negotiated price, looking at alternatives, or validating further.

The starter code (`starter_agent.py`) gives one search and one model reply. Our code (`evaluator.py` and `eval/`) adds query planning, full-page price checks, a judge, a price-history store, and a purchase recommender.

## Architecture

Search and checking run in one pipeline. The purchase recommender reads only what the pipeline has verified, plus the PM's memory file. Tracing runs alongside and is off unless its keys are set.

```mermaid
flowchart LR
  subgraph IN[" Inputs "]
    Q["PM question"]
    M["PM memory"]
  end
  subgraph SEARCH[" Search "]
    P["Query plan"] --> T["Tavily search"] --> F["Filter off-topic and undated"]
  end
  subgraph VERIFY[" Verify "]
    X["Full page text"] --> C["Price check against cited page"] --> J["LLM judge with verbatim evidence"]
  end
  subgraph STORE[" Verified stores "]
    S[("Price history and gate")]
    V[("Purchases and SSO facts")]
  end
  subgraph OBS[" Observability "]
    L["Langfuse traces: one per run, span per search, generation per model call"]
  end
  subgraph DECIDE[" Decide and show "]
    R["Purchase recommender"] --> U["Main page and purchase page"]
  end
  Q --> P
  F --> X
  J --> B["Brief with source IDs"]
  C --> S
  S --> R
  V --> R
  M --> R
  P -.-> L
  J -.-> L
  classDef inp fill:#eef3ee,stroke:#1f5f4a,color:#1d1c19,stroke-width:2px
  classDef srch fill:#dce8f7,stroke:#2b5c8a,color:#14273d,stroke-width:2px
  classDef ver fill:#dff2e6,stroke:#1f6b45,color:#11301f,stroke-width:2px
  classDef stor fill:#f7e9c6,stroke:#a7770f,color:#3a2a06,stroke-width:2px
  classDef out fill:#1f5f4a,stroke:#123d2f,color:#ffffff,stroke-width:2px
  class Q,M inp
  class P,T,F srch
  class X,C,J,B ver
  class S,V,L stor
  class R,U out
```

Technical statement: [TECHNICAL_STATEMENT.md](TECHNICAL_STATEMENT.md).

## Results

These pages are published from this repo. They are private to the account that published them.

- **Story** (search product comparison: the decision, architecture, and roadmap): https://claude.ai/artifact/LhBFRmp7YKZUL6LivMdeh3
- **Results** (four tabs: starter vs ours, search outputs, evaluation, purchase recommendations): https://claude.ai/artifact/3afXof9TfKhpmUoa7kNXNw

To rebuild them locally:

```bash
python3 eval/build_ui.py              # writes eval/ui/index.html (main results page)
```

## Setup

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # then fill in the keys
.venv/bin/python eval/purchases/db.py --seed   # builds the purchase database (git-ignored)
```

Copy `.env.example` to `.env` and fill in:

- `TAVILY_API_KEY` (required): search and page extraction.
- `NEBIUS_API_KEY` (required): model calls for the brief and the judge.
- `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL` (optional): tracing. Leave the keys empty to turn tracing off.
- `PIPELINE_JUDGE_MODEL` (optional): the model that checks each claim. Defaults to Kimi, the model that scored best against the 50-claim blind check.

`.env` is git-ignored. Do not commit keys.

## Run

```bash
.venv/bin/python evaluator.py --product Linear --category "project management"   # our brief, written to runs/
.venv/bin/python starter_agent.py "What does Linear cost per user?"               # the starter, for comparison
.venv/bin/python -m unittest discover -s tests -p "test_*.py"                     # unit tests (CI runs these on every push)
```

Each evaluator run writes `brief.md` and `run.json`. The run record includes the writer and judge models, the search settings, the judge's verdict counts, and the structured pricing facts.

## Layout

| Path | What it holds |
|---|---|
| `evaluator.py` | Query plan, search, filters, price check, brief |
| `starter_agent.py` | The provided starter code, kept for comparison |
| `eval/llm_judge.py` | LLM judge: checks each claim against full page text |
| `eval/store.py` | Price history: gate, alerts, review queue (`eval/data/prices.db`) |
| `eval/purchases/` | Purchases, verified SSO facts, PM memory, recommender |
| `eval/build_ui.py` | Builds the results page (`eval/ui/index.html`) |
| `eval/tune/` | Hand labels, labelling rule, judge scores |
| `runs/` | Output of each evaluator run (`brief.md`, `run.json`) |
| `tests/` | Unit tests (run in CI from `.github/workflows/tests.yml`) |

## Documentation

- `ENHANCEMENTS.md`: each shortcoming in the starter, the change made, the evidence, and what is still open.
- `PROGRESS.md`: the timeline and decisions, including the open live Langfuse trace check.
- `docs/search-flow.md`: side-by-side search comparison.

## Status

- Open items are listed in `ENHANCEMENTS.md` and `PROGRESS.md`.
