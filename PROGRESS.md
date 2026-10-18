# Progress: Tavily FDE Take-Home

Working log for the take-home. Update the checkboxes and the log as we go. Product-level shortcomings and their fixes are tracked in `ENHANCEMENTS.md`.

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
| "Similar" definition | Decided | Same category and same target customer. Must be stated in the write-up. |
| Target user | Decided | PM at a dev-tool or SaaS company, deciding how to position or price against a launch. |
| Dimensions evaluated | Decided | Pricing and plans (first focus), competitive landscape, recent reception. Audience demand dropped: weak and hard to check from search. |
| Output format | Decided | Markdown brief. Numbered citation per claim. Unsupported claims listed separately. Scored pricing table only if time allows. |
| Citation policy | Proposed | Every claim links to a URL. Unsupported claims are flagged. |
| Model/provider | Current | Nebius via `ChatNebius` (works now) |
| Observability standard | Decided: Langfuse | Open source and self-hostable. Its Python SDK disables itself without keys, so the tool still runs. LangSmith is the LangChain-native option. OpenTelemetry needs a separate backend to view traces. |

## Plan

### Phase 0: Repo setup
- [x] Initialize git repo (branch `main`, no commits yet)
- [x] `.gitignore` excludes `.env`, `.venv/`, `__pycache__/`, `starter_agent.py`, and the assignment doc
- [ ] First commit (waiting on your go-ahead)
- [ ] Create a GitHub remote and push (waiting on your go-ahead)

### Phase 1: Understand the starter
- [x] Read the rest of `starter_agent.py` (streaming and output logic)
- [x] Run the starter end-to-end and save a sample output for comparison (`baseline/starter_output.txt`)

### Phase 2: Scope
- [x] Pick target user
- [x] Pick the 3 dimensions and their Tavily queries
- [x] Pick output format
- [x] Write the one-paragraph scope statement for the technical write-up (in the Log below)

### Phase 3: Build
- [x] Add a launch-evaluation prompt and input (product name and description) (`evaluator.py`)
- [x] Add a query plan: one or more Tavily searches per dimension (`plan_searches`)
- [x] Return findings with numbered source citations (source IDs S1, S2, ... from Tavily URLs)
- [x] Flag claims that have no supporting source (`check_claims`, "Unsupported claims" section)
- [x] Format the final brief (`render_brief`; run record in `run.json`)
- [x] Live run with real keys (run `linear-20261018-110358`: 44 sources, 20 cited claims, 0 errors)

### Phase 4: Verify
- [ ] Build a test set of 5–10 launches with known reception or outcomes
- [ ] Run the evaluator on each and record results
- [ ] Score: are findings supported by their cited sources? (before and after any change)
- [ ] Record what the tool gets wrong, too

### Phase 4b: Observability (bonus)
- [x] Add tracing for each run: query plan, each Tavily call, each extraction, and the aggregation step (Langfuse: one root trace `launch_evaluation`, a span per Tavily search, a generation per model call)
- [x] Pick a standard and record why (Langfuse, see Decisions)
- [ ] Live trace check with keys: confirm the trace shows in Langfuse with all steps
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
  - Phase 1 done. Read the starter and ran the baseline. Findings are in `ENHANCEMENTS.md`: citations are not tied to claims, the search window was one month for a yearly question, and the query used the wrong year.
  - Phase 2 done. Scope statement: given a product name and description, the evaluator finds similar products (same category, same target customer) and produces a sourced Markdown brief on three dimensions: pricing and plans (first focus), competitive landscape, and recent reception. Every claim has a numbered citation to a URL Tavily returned. Claims without a source are listed as unsupported. The brief does not predict sales or causal outcomes, and it does not measure audience demand.
  - Phase 3 built (not yet run live). `evaluator.py` runs discovery, a fixed query plan (pricing per product, comparison per similar product, reception with a one-year window), then writes a brief whose claims cite source IDs. Claims with no valid ID go to an "Unsupported" section. Each run writes `brief.md` and `run.json` under `runs/`. Unit tests (15, `tests/test_evaluator.py`) pass. The live run needs `TAVILY_API_KEY` and `NEBIUS_API_KEY` in the terminal.
  - Added Langfuse tracing (Phase 4b). Root trace `launch_evaluation`, a span per Tavily search, a generation per model call. Setup: create a free project at Langfuse, then set `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` (and `LANGFUSE_BASE_URL` if self-hosted) in the terminal or `.env`. Without keys, the tool runs and tracing is off. Offline smoke run passed. A live trace is not verified yet.
  - Live run on "Linear" found 43 sources and 3 similar products, but the brief had no claims. The Langfuse traces showed the brief call returning empty. The run record says `finish_reason=length` with 4096 output tokens used, so the model used its whole output budget and wrote no text. Raised the limit to 16384. Re-run at 11:03 worked: run `linear-20261018-110358` has 44 sources, 20 cited claims, 0 errors. The Langfuse trace shows the brief call returning JSON.
  - Similar-product fix: the run picked Height, which has shut down, so its pricing search returned retired prices. The similar-products prompt now excludes discontinued products. A code check also drops any candidate that a retrieved source describes as shut down, and records it under `excluded_retired` in `run.json`. 18 unit tests pass. Live re-run `linear-20261018-110743`: similar products are Jira, YouTrack, GitHub Issues; no Height; 44 sources, 21 supported claims, 0 unsupported, 0 errors. The prompt change did the work. The code check did not trigger, so it is still covered only by unit tests.
  - Phase 4 spot check of the pricing claims in run `linear-20261018-110743`, against the full text of each cited source:
    - Free plan (unlimited members, 2 teams, 250 issues): supported by S7, S31, S44.
    - Basic at $10/user/month billed yearly, removes the issue limit, up to five teams: supported by S7, S8, S31.
    - Business at $16/user/month with unlimited teams, guests, Triage Intelligence, Insights, Linear Asks, support-desk integrations: supported by S31.
    - Enterprise is custom and annual-only: supported by S7 and S31. S10 gives custom pricing but not the annual-only detail.
    - Coding sessions and Loops consume AI credits: supported by S31. The claim says "prepaid," which none of the cited text says. This is an overstatement.
    - Guest accounts need Business and are billed as regular members: supported by S44.
    - All cited sources are third-party blogs. None is Linear's own pricing page, so the prices need checking there.
  - Phase 4 spot check of the reception claims in run `linear-20261018-110743`:
    - G2 4.6/5 from 122 reviews and Capterra 4.4/5 from 5 reviews: supported by S44.
    - "the fastest of any major project management tool" and "most teams are productive within an hour": supported by S42 (quotes match).
    - Hacker News "much much better than all the competition": the quote is in S35, but the comment is dated June 30, 2022. It is not recent reception, so it should be dropped from the Recent reception section.
    - Editorial score 4.7/5 from Bundl: supported by S43.
    - Linear Agent (March 24, 2026), Shared Skills (June 4, 2026), Coding Sessions GA (June 11, 2026): supported by S41.
    - Gap: the reception claims come from review sites and blogs, not user data. A 2022 comment shows the date filter does not guarantee recent sources.
  - Date filter for reception: the reception search now sends `start_date` (365 days back) instead of `time_range`, and results with a `published_date` before the cutoff are dropped. Undated results are kept. This was added after a 2022 Hacker News comment reached the Recent reception section. 19 unit tests pass. The live re-run is not done yet.
  - Run `linear-20261018-111021` (with the date filter): the Hacker News comment is gone, and the reception claims are sourced. But Height came back as a similar product, and `excluded_retired` was empty. Cause: the retirement check ran only on the discovery results, which don't say Height shut down. The shutdown text (S40) was retrieved later, in the comparison step. Fix: before the check, each candidate gets its own search ("<name> discontinued or shut down"). `published` is now saved per source in `run.json`, so reception dates can be checked. 19 unit tests pass. Live re-run not done yet.
  - Run `linear-20261018-111257`: the status search worked, but the retirement check now excluded Jira, YouTrack, and Plane, leaving only GitHub Issues. Replaying the check on the saved sources found: "Plane" matched inside "airplanes" (a plain bug, now fixed with word boundaries); Jira matched "Jira Data Center shutdown" (a deployment type, not the product); YouTrack matched "discontinued support for new installations" (a feature). The sentence-level rule fixed the cross-page matches but not these. Height is still correctly excluded. All reception dates in this run are missing (`published` is empty), so the date filter is not verified. The earlier removal of the 2022 comment came from the sources not being retrieved, not from the filter. 21 unit tests pass.
  - Decision: the keyword check is replaced with an LLM status judge. Each candidate's status-search results go to the model, which returns active, retired, or unknown with a source ID. Only "retired" excludes a candidate. "Unknown" is kept and recorded. The verdicts are saved as `candidate_status` in `run.json`. 23 unit tests pass (status parsing included). Live run not done yet.
  - Run `linear-20261018-111619` (LLM status judge): similar products are Jira, GitHub Issues, YouTrack. Height is excluded as retired, citing S16, which says it went offline on 24 September 2025. Checked the cited sources: Height is well supported. Jira "active" cites S7, an article about the end of Jira Data Center, not Jira Cloud. The verdict is probably right, but the citation is weak. GitHub Issues cites GitHub's issue docs, and YouTrack cites its Wikipedia page, which lists a 2024 release. Plane is unknown with no source, so it was not chosen. 69 sources, 28 supported claims, 0 unsupported, 0 errors.
  - Phase 4 check of pricing and competitive claims, run `linear-20261018-111619`. Most are supported by their sources. Problems:
    - HN claim: "one commenter described YouTrack's UX as quite bad and Linear as much much better" merges two commenters in a June 30, 2022 thread (S65). It is stale and sits in the competitive section, which has no date filter.
    - Coding agent tier: "built-in coding agent on Business and above" (S56) conflicts with an earlier run's source that lists Basic, Business, and Enterprise. Needs a check against this run's sources.
    - Weak sources: "sleek interface" is from monday.com, a competitor blog, and "activity stream" is from a vendor blog.
    - Not fully checked: the Enterprise "custom pricing" part (S35) and the GitHub Issues open-source positioning (S59).
  - Fixes applied: competitive searches now use the same 365-day `start_date` cutoff as reception. The brief prompt now allows one quote per claim, attributed only to its source, and never merges quotes from different people. 24 unit tests pass. Live re-run not done yet.
  - Coding-agent tier is unresolved in run `linear-20261018-111619`. The t0ggles comparison (S56) says Business and above. The SIIT review (S66) says Basic, Business, and Enterprise. Linear's changelog (S67) excerpt does not name tiers. The claim needs a primary source, or the brief should say the sources disagree.
  - Run `linear-20261018-112014`: similar products Jira, GitHub Issues, YouTrack; Height retired. 68 sources, 18 supported claims, 0 unsupported, 0 errors. No Hacker News quote claim appears. But no source in the run has a `published` date, including the competitive and reception sources. The date cutoff therefore filters nothing here, and recency is unverified. Open decision: flag undated sources in the brief, or require a date for reception claims.
  - Option 1 applied: undated sources are flagged in the brief. Each source line shows its date or "date unknown", and any claim whose cited sources are all undated gets a "(date unknown)" note. `published` is saved per source in `run.json`. 25 unit tests pass. Replaying run `linear-20261018-112014` through the new renderer shows the flags. Live re-run not done yet.
  - Run `linear-20261018-112447`: similar products Jira, GitHub Issues, YouTrack; Height retired. 68 sources, none dated, so every claim is flagged "date unknown," as intended. 0 unsupported claims. Two problems: (1) the brief is mostly long quotes, a side effect of the earlier "one quote per claim" rule. The prompt now asks for paraphrase, with quotes of at most 10 words. (2) The first brief attempt hit the 16,384-token output limit with an empty reply, and the second attempt worked. The model spends most of its output budget on reasoning. Live re-run not done yet.
  - Takeaway: these tools simulate consumers. Our differentiator is sourced, checkable evidence from Tavily, plus an eval that measures whether claims are supported. Avoid claiming causal predictions. A 2025 arXiv paper found persona simulations can fail on causal questions.

## Build record

The assignment asks for a record of how the project was built: chat history, session logs, or equivalent.

- [ ] Keep the Log section above updated after each working session (date, what changed, what was decided, what was verified or failed).
- [ ] Record each decision in the Decisions table when it's made, with the reason.
- [ ] Save the chat history at the end of the project (in Claude Code, `/export` writes the conversation to a file).
- [ ] Keep the eval results (inputs, outputs, scores) in the repo, so the record shows verification, not only claims.
- [ ] Note which AI-generated output was checked, and how, in the technical statement.

## Open questions

None for Phase 2. Phase 3 will refine the queries once the first run shows what Tavily returns.
