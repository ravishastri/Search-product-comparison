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

## Plan

### Phase 0: Repo setup
- [x] Initialize git repo (branch `main`, no commits yet)
- [x] `.gitignore` excludes `.env`, `.venv/`, `__pycache__/`, `starter_agent.py`, and the assignment doc
- [x] First commit (`4eda3e2`, plus `b1e693b` and `7516234` on branch `evaluator-brief-fixes`)
- [x] Create a GitHub remote and push (`origin`, branch `evaluator-brief-fixes` pushed; not merged to `main`)

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
- [x] Live run (run `linear-20261018-110358`: 44 sources, 20 cited claims, 0 errors)

### Phase 4: Verify
Decided: SaaS is the main eval domain (pricing has ground truth; matches the target user). The starter baseline is included, so improvement is measured on the same products and judge.

- [x] 4a. Golden set: 8 SaaS products in the issue-tracker category. Captured 2026-10-18 with Playwright (accessibility snapshots in `eval/golden/`): Linear, Jira, Plane, Shortcut, ClickUp, Asana, Trello, YouTrack. These pages are the ground truth.
- [~] 4b. Ground-truth sheet: `eval/golden/ground_truth.json`. Partial and extracted, not hand-written: I pulled price lines from the captured snapshots, and each fact quotes its line. Plan names are inferred for most rows and marked `context_verified: false`. Shortcut has no prices (not captured). A human needs to review it before scoring.
- [ ] 4c. Starter baseline: run `starter_agent.py` on the same 8 products. Save raw outputs to `eval/runs/starter/`.
- [ ] 4d. Evaluator run: run `evaluator.py` on the same 8 products. Save to `eval/runs/evaluator/`.
- [~] 4e. Judge. Deterministic part built: `eval/judge.py` checks cited IDs exist, prices in a claim appear in its cited text, quotes are verbatim, and sources are dated and not stale. Not built yet: the LLM judge (claim vs full cited text, verdict plus evidence quote, different model from the generator). Framework choice: no RAGAS yet. RAGAS faithfulness needs its own model setup and dataset format, and the deterministic checks cover the pricing failures we have seen. Add RAGAS as a cross-check once the LLM judge exists.
- [ ] 4f. Judge calibration: hand-label about 50 claims. Measure agreement with the judge. Report it with the scores. Seed: the claims already hand-checked this session.
- [ ] 4g. Metrics for starter and evaluator, under the same judge: claim support rate, contradiction rate, citation precision, staleness rate, and recall of ground-truth prices.
- [ ] 4h. Ablation: turn off one enhancement at a time (date rule, status judge, paraphrase rule) and record the change in each metric.
- [ ] 4j. Record what the tool gets wrong, too.

### Phase 5: Deliver
- [ ] Clean up the repo (no `starter_agent.py`)
- [ ] Write the technical statement (approach, reasoning, value, limits)
- [ ] Save the build record (chat history or session log)
- [ ] Final read-through: remove anything not verified

## Log

- **Date:** 2026-10-18
  - Read the assignment. Chose Option 1.
  - Proposed a product launch evaluator, narrowed to fixed dimensions with cited claims.
  - Created this file.
  - Checked three YC synthetic-consumer companies (Foresight, Studio, Auxos) for market context. Their claims are self-reported and mostly unverified. Foresight's batch is unclear across sources. Studio's public detail is thin. Auxos has no independent accuracy evidence.
  - Picked the project scope: a product plus aggregated similar products, with pricing as the first focus. Rejected image A/B testing (search can't see the catalog or run experiments).
  - Added a Phase 0 (repo setup) and an optional observability phase.
  - Initialized git on `main`. Added `.gitignore`. The starter and assignment doc are excluded from the repo, as the assignment asks.
  - Phase 1 done. Read the starter and ran the baseline. Findings are in `ENHANCEMENTS.md`: citations are not tied to claims, the search window was one month for a yearly question, and the query used the wrong year.
  - Phase 2 done. Scope statement: given a product name and description, the evaluator finds similar products (same category, same target customer) and produces a sourced Markdown brief on three dimensions: pricing and plans (first focus), competitive landscape, and recent reception. Every claim has a numbered citation to a URL Tavily returned. Claims without a source are listed as unsupported. The brief does not predict sales or causal outcomes, and it does not measure audience demand.
  - Phase 3 built (not yet run live). `evaluator.py` runs discovery, a fixed query plan (pricing per product, comparison per similar product, reception with a one-year window), then writes a brief whose claims cite source IDs. Claims with no valid ID go to an "Unsupported" section. Each run writes `brief.md` and `run.json` under `runs/`. Unit tests (15, `tests/test_evaluator.py`) pass. The live run needs both service keys set.
  - Live run on "Linear" found 43 sources and 3 similar products, but the brief had no claims. The run record showed the output limit reached with no text, so the model used its whole output budget and wrote nothing. Raised the limit to 16384. Re-run at 11:03 worked: run `linear-20261018-110358` has 44 sources, 20 cited claims, 0 errors.
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
  - Brief fixes (session 2026-10-18, later). The first brief attempt still hit the output limit on run `linear-20261018-112447`. Raised the output limit from 16384 to 32768. The brief prompt now requires paraphrase with no quotation marks, which replaces the one-quote-per-claim rule. 25 unit tests pass.
  - Live run `linear-20261018-113305` (run by the user in their terminal): 0 errors, so the first attempt finished. 69 sources. The brief has 0 quotation marks, down from 17 in the previous run. Claims still cite source IDs. All sources are undated, so every claim carries "(date unknown)". Not yet checked: claim support against the cited text, and the Plane "roughly 40% less than Linear's Basic tier" comparison, and the Huly "discontinued" line.
  - Git: fix committed as `b1e693b` (evaluator, tests, run `linear-20261018-113305`). Remaining project files committed as `7516234`, excluding `starter_agent.py`, which is gitignored. Branch `evaluator-brief-fixes` pushed to `origin`. The commit includes `.playwright-mcp/`, which holds browser snapshots from the Playwright session. Not yet removed.
  - Phase 4 source check, run `linear-20261018-113305` (Playwright, all 27 sources cited in claims). Checks were keyword-level: each page was searched for the figures or terms in its claims, so these results show that the terms appear, not that each claim is fully confirmed.
    - Supported: S2 ("fastest, most opinionated"), S11 (hosted Huly shut down), S31 ($5,000–$70,000 range), S32 and S35 (Basic $10, Business $16, 250 issues, 2 teams), S40 (Plane $6), S46, S49, S50 (GitHub Team $4, Enterprise $21), S57 and S59 and S60 (Huly Docker, AGPL, EPL), S61 (100 ms), S63 and S65 (GitHub integration), S66 and S67 (Linear Agent, Shared Skills, Coding Sessions dates), S68 (4.7 rating), S69 (G2 4.6 from 122 reviews, Capterra 4.4 from 5).
    - Wrong or unsupported: S5 says Linear has an official MCP server. The page calls Agiflow "the MCP-native alternative to Linear," which is the competitor's own marketing. Remove the claim.
    - Conflict not shown in the brief: S69 lists Linear Basic at $50 a month for a team, while the brief gives $10 per user per month (S32, S35). Both are from real sources. The brief should report the conflict.
    - Weak or unchecked: S55 (brand names only), S52, S54 (MIT matched), S62, S66's triage wording, the S57 "syntax highlighting" claim, and the S65 "sleek interface" and "activity stream" wording, which the Commonwealth page does not contain.
    - Takeaway: the pipeline finds real sources, but a fraction of claims carry stale figures, a wrong attribution, or an unshown conflict. Phase 4 needs claim-level scoring against the full cited text, not keyword checks.
  - Golden set and deterministic judge (session 2026-10-18). Golden set: 8 pricing pages captured (`eval/golden/`). Shortcut prices were not captured. `ground_truth.json` was extracted from the captures and needs review. Judge (`eval/judge.py`) on run `linear-20261018-113305`: 45 claims, all cited IDs valid, 6 price claims, 1 with a price not in its cited text, 0 quoted claims, 0 dated claims, 0 stale claims. Ground-truth price recall 2 of 3, missing the $0 free plan. The judge's flagged claim is "Spendflo ... range from $5,000 to $70,000". The $70,000 is on the page; $5,000 is not in the snippet, and my earlier full-page check did not find it either, so the lower bound looks unsupported. The LLM judge is not built yet.

## Build record

The assignment asks for a record of how the project was built: chat history, session logs, or equivalent.

- [ ] Keep the Log section above updated after each working session (date, what changed, what was decided, what was verified or failed).
- [ ] Record each decision in the Decisions table when it's made, with the reason.
- [ ] Save the chat history at the end of the project (in Claude Code, `/export` writes the conversation to a file).
- [ ] Keep the eval results (inputs, outputs, scores) in the repo, so the record shows verification, not only claims.
- [ ] Note which AI-generated output was checked, and how, in the technical statement.
