# Progress: Tavily FDE Take-Home

Working log for the take-home. Update the checkboxes and the log as we go.

## Assignment

- **Option:** 1 (improve the existing app)
- **Project:** Product launch evaluator. Researches a product's market, audience, consumption, and strengths and weaknesses, using Tavily.
- **Deliverables:** GitHub repo (exclude `starter_agent.py`), technical statement, build record, and verification evidence.
- **Time budget:** 4–6 hours. Prefer a small thing done well.

## Decisions

| Decision | Status | Notes |
|---|---|---|
| Option 1 (improve app) vs Option 2 (explainer) | Decided: Option 1 | Builds on the existing CLI |
| Project scope | Decided: product + similar-product aggregation | Input a product. Find similar products. Extract and compare pricing, plans, and features, with a sourced summary. Pricing is the first focus. |
| "Similar" definition | Open | Proposed: same category and same target customer. Must be stated in the write-up. |
| Target user | Open | Example: PM at a dev-tool company. Drives what "good" means. |
| Dimensions evaluated | Open | Proposed: competitive landscape, audience demand signals, recent reception of similar launches |
| Output format | Open | Markdown brief, scored table, or both |
| Citation policy | Proposed | Every claim links to a URL. Unsupported claims are flagged. |
| Model/provider | Current | Nebius via `ChatNebius` (works now) |

## Plan

### Phase 0: Repo setup
- [x] Initialize git repo (branch `main`, no commits yet)
- [x] `.gitignore` excludes `.env`, `.venv/`, `__pycache__/`, `starter_agent.py`, and the assignment doc
- [ ] First commit (waiting on your go-ahead)
- [ ] Create a GitHub remote and push (waiting on your go-ahead)

### Phase 1: Understand the starter
- [ ] Read the rest of `starter_agent.py` (streaming and output logic)
- [ ] Run the starter end-to-end and save a sample output for comparison

### Phase 2: Scope
- [ ] Pick target user
- [ ] Pick the 3 dimensions and their Tavily queries
- [ ] Pick output format
- [ ] Write the one-paragraph scope statement for the technical write-up

### Phase 3: Build
- [ ] Add a launch-evaluation prompt and input (product name and description)
- [ ] Add a query plan: one or more Tavily searches per dimension
- [ ] Return findings with numbered source citations
- [ ] Flag claims that have no supporting source
- [ ] Format the final brief

### Phase 4: Verify
- [ ] Build a test set of 5–10 launches with known reception or outcomes
- [ ] Run the evaluator on each and record results
- [ ] Score: are findings supported by their cited sources? (before and after any change)
- [ ] Record what the tool gets wrong, too

### Phase 4b: Observability (bonus)
- [ ] Add tracing for each run: query plan, each Tavily call, each extraction, and the aggregation step
- [ ] Pick a standard (LangSmith or OpenTelemetry) and record why
- [ ] Use traces to debug one failed extraction and note the fix in the Log

### Phase 5: Deliver
- [ ] Clean up the repo (no `starter_agent.py`)
- [ ] Write the technical statement (approach, reasoning, value, limits)
- [ ] Save the build record (chat history or session log)
- [ ] Final read-through: remove anything not verified

## Log

- **Date:** 2026-10-18
  - Read the assignment. Chose Option 1.
  - Proposed a product launch evaluator, narrowed to fixed dimensions with cited claims.
  - Confirmed the Tavily key works. The Nebius key failed earlier and now works.
  - Created this file.
  - Checked three YC synthetic-consumer companies (Foresight, Studio, Auxos) for market context. Their claims are self-reported and mostly unverified. Foresight's batch is unclear across sources. Studio's public detail is thin. Auxos has no independent accuracy evidence.
  - Picked the project scope: a product plus aggregated similar products, with pricing as the first focus. Rejected image A/B testing (search can't see the catalog or run experiments).
  - Added a Phase 0 (repo setup) and an optional observability phase.
  - Initialized git on `main`. Added `.gitignore`. The starter and assignment doc are excluded from the repo, as the assignment asks.
  - Takeaway: these tools simulate consumers. Our differentiator is sourced, checkable evidence from Tavily, plus an eval that measures whether claims are supported. Avoid claiming causal predictions. A 2025 arXiv paper found persona simulations can fail on causal questions.

## Build record

The assignment asks for a record of how the project was built: chat history, session logs, or equivalent.

- [ ] Keep the Log section above updated after each working session (date, what changed, what was decided, what was verified or failed).
- [ ] Record each decision in the Decisions table when it's made, with the reason.
- [ ] Save the chat history at the end of the project (in Claude Code, `/export` writes the conversation to a file).
- [ ] Keep the eval results (inputs, outputs, scores) in the repo, so the record shows verification, not only claims.
- [ ] Note which AI-generated output was checked, and how, in the technical statement.

## Open questions

- Who is the target user?
- Which 3 dimensions, and which queries for each?
- Markdown brief, scored table, or both?
