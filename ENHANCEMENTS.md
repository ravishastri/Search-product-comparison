# Enhancements

The starter (`starter_agent.py`) answers a product question with a search and a model reply. Its answers look sourced, but nothing checks them. This document lists each shortcoming we found, the change we made, the evidence that the change altered the output, and what is still not solved. Process and timeline live in `PROGRESS.md`.

The goal is not a guarantee of truth. The goal is that every claim in the output can be traced to a source, a date, and a check, and that known failures are visible instead of hidden.

Status values: `Open`, `Partial`, `Done`, `Deferred`.

## Shortcomings in the starter, and what we changed

| # | Shortcoming in the starter | Why it misleads | Change we made | Evidence | Status / what's still missing |
|---|---|---|---|---|---|
| 1 | Citations are optional. The system prompt says "include source URLs when available." | Figures appear with no link to any source. | Every claim must cite source IDs (S1, S2, ...) that the search returned. Claims with no valid ID go to an "Unsupported" section. | In the baseline, specific figures (Pew click rates, AI Mode share, 161.5M forecast) had no link. | **Partial.** The check confirms IDs exist, not that the source supports the claim. Spot checks found support gaps (see row 3). |
| 2 | Tool results are printed, not stored. | Nothing can be audited after a run. | Each run writes `brief.md` and `run.json`: queries, every source with URL and date, status verdicts, and errors. | Run records were used to diagnose a truncated reply (`finish_reason=length`) and to trace the source behind each claim. | **Done** for storage. Search settings are not yet recorded per run (row 8). |
| 3 | No eval loop. Nothing measures whether answers are correct. | We cannot say how often the output is wrong. | Manual spot checks of pricing, reception, and status claims against the full text of the cited pages. | Spot checks on the Linear run found: a 2022 comment presented as recent, and one overstated claim ("prepaid" credits). | **Open.** The spot checks are manual and cover a few claims. The Phase 4 test set (5–10 launches, scored) is not built. |
| 4 | Output is free text. | Code and reviewers cannot check fields such as price or plan. | Claims are structured JSON with dimension, text, and source IDs before they are rendered. | Unsupported claims are separated automatically. | **Partial.** The brief is still Markdown. Prices are not parsed into fields. |
| 5 | `truncate` affects only display. The model sees full tool results. | The display can hide what the model used. | The model receives each source's snippet, capped at 600 characters, and the run records the sources. | Source IDs in the brief map to records in `run.json`. | **Partial.** The cap means the model sees less than the full result. We do not log which snippet text was sent. |
| 6 | No query planning. One question is sent as-is. | Broad questions get shallow coverage. | A fixed plan: one pricing search per product, one comparison per similar product, and one reception search. Similar products are checked for status with their own searches. | Live runs found three similar products each time. The status step excluded Height as retired, citing a source that says it went offline. | **Partial.** The plan is the same for every product. Query templates per category are not built. |
| 7 | No retries or error handling beyond one generic catch. | One failed call ends the run. | Each failed step is recorded in `errors` and the run continues. Empty model replies raise a specific error. | `run.json` recorded the first-attempt empty reply on run `linear-20261018-112447`, which made the cause visible. | **Partial.** No retries with backoff yet. |
| 8 | Search settings are hard-coded or defaulted. | Results depend on settings no one chose on purpose. | Search depth is fixed at `advanced`, and results per query at 5. | Search settings are fixed for every run. | **Partial.** Search depth and result count are not options and are not recorded. |
| 9 | No tests. | Changes can break behavior silently. | 28 unit tests: query planning, source dedup and date rules, parsing, citation checks, status parsing, and brief rendering. | All 28 pass on the current code. | **Partial.** Tests check logic, not whether claims are true. |
| 10 | Search window does not match the question. The baseline used a one-month window for a yearly question, and the query said 2025 in October 2026. | The answer covers the wrong period. | Reception and competitive searches use a 365-day window from today, with the year taken from today's date. Those searches use Tavily news mode and require a published date. | Unit tests check the window and the news-mode setting. | **Partial.** Not yet verified that news mode returns dates on a live run. If it does not, these sections will be empty. |

## Problems found while building (not in the starter's list)

These came from checking the outputs, after the starter review. Each one is a way the output could mislead a reader.

- **Empty brief.** The model used its whole output budget on reasoning and returned no text. Fixed by raising the output limit. Cost: longer calls. We have not compared a model without long reasoning.
- **Retired products treated as similar products.** Height (shut down) was recommended as a similar product. A keyword check excluded it, but also falsely excluded Jira, YouTrack, and Plane (matched inside "airplanes" and an unrelated "shutdown" phrase). Replaced with a status judge that reads each candidate's results.
- **Stale sources presented as current.** A 2022 Hacker News comment appeared in "recent reception." The fix: reception and competitive searches use news mode and drop results with no published date. Pricing is not filtered, so a 2025 price (S41) can still appear as current.
- **Quote-heavy briefs.** One quote per claim produced long copied passages. Changed to paraphrase with no quotation marks; the Linear brief went from 17 quoted lines to 0.

## What counts as "closer to true" here

- A claim with no source is flagged, not shown as fact.
- Every claim with a source can be traced to a URL and a date in `run.json`.
- Known failures are recorded: stale sources, rumor-based verdicts, and the pricing gap.
- Support is checked by hand on a sample. Automated checks confirm only that IDs exist.

What is not yet true: we have no measured accuracy rate. The next step is the Phase 4 test set, with claims scored against their cited text, before and after each change.

## Problems found in runs, and fixes

Each run's problems are listed with the fix and its status. Runs are listed in the order they were done.

| Run | Problem | Fix | Status |
|---|---|---|---|
| `linear-20261018-113305`, `-142022` | The brief says Linear's range is "$5,000 to $70,000" (cited S26, Spendflo). The $70,000 is on the page, but $5,000 is not in the cited text or the full page. It came back in both runs. | Claims whose prices are not in the cited text are labeled "(price not in cited text)" in the brief. Unit test added. | **Partial.** The label is shown, but the claim is still in the brief. Removing it needs the judge (row 6 below). |
| `linear-20261018-142022` | Three price claims cite sources whose snippets lack the figure, even though the figures are correct. Examples: Basic $10 (S52), and YouTrack $5.40 and $4.50. | Same label as above. The judge reports the rate (`prices_in_cited_text`). | **Partial.** The snippet is the limit. Real fix is row 6. |
| `linear-20261018-142022` | The ground-truth check could not find the free plan, because "$0" never appears in the brief. | Fact-level match term ("free") added to the ground truth. | **Partial.** "free" is a loose match, so recall 1.0 is weak evidence. A stricter check is needed. |
| `linear-20261018-142022` | Dated claims went from 0% to 58% after the news-mode change. Pricing claims are still undated, because pricing searches do not use news mode. | None needed; this is expected. Confirms the news-mode date setting works. | **Done** for news sections. Pricing is still undated by design. |
| All runs | The judge checks 600-character snippets, not full pages, so "not in cited text" can mean "not in the snippet". | Fetch and store full page text for each cited source, then judge against that. | **Open**, the highest-priority fix. |

### Runs after the key fix (Linear, 2026-10-18)

| Run | Problem | Fix | Status |
|---|---|---|---|
| Judge (`eval/judge.py`) | The claim pattern allowed only one trailing "(…)" note. A claim with two notes ("(date unknown) (price not in cited text)") was dropped silently, so the judge counted 33 claims in a run that had 34. | Pattern now accepts any number of trailing notes. Both Linear runs rejudged. Earlier judge numbers for `142022` are superseded. | **Done** |
| Evaluator `linear-20261018-143031` | None blocking. All 34 claims have valid IDs, 0 errors. The `$5,000` range claim is still in the brief but is now labeled "(price not in cited text)". | Label is working as designed. Removing such claims still needs the LLM judge (full page text). | **Partial** |
| Starter baseline (`eval/runs/starter/linear.txt`) | Output is free text with inline URLs, not source IDs, so the judge cannot score it. Measured without claim extraction: 61 bullet or table lines, 36 (59%) with a URL. 37 price mentions. All 3 ground-truth facts present. No `$5,000` claim. | Build a claim extractor for free-text output, then judge both systems with the same LLM judge against full page text. | **Open**, next step |

## Results: starter vs evaluator (Linear, LLM judge)

Both systems were judged by `eval/llm_judge.py`, which reads the full text of each cited page and accepts a verdict only when its quoted evidence is verbatim in that text.

| System | Claims | Supported | Contradicted | Not stated | No source text | Support rate |
|---|---|---|---|---|---|---|
| Starter | 135 | 88 | 4 | 30 | 13 | 65% |
| Evaluator (`linear-20261018-143031`) | 34 | 30 | 0 | 3 | 1 | 88% |

Caveats, to state in the interview:
- The starter's answer is much longer (135 claims against 34), so the rates are not counts from the same set of claims.
- The judge is the same model that wrote the starter's and the evaluator's text. It has not been checked against hand labels yet.
- Page text is capped at 20,000 characters per URL, so a claim whose evidence sits later on the page can be marked "not stated".

### Problems from these runs, and fixes

| Run | Problem | Fix | Status |
|---|---|---|---|
| Starter judge, first run | The judge ran for about 85 minutes with no output and had to be stopped. It had no per-call timeout and printed nothing until the end. | Per-call timeout (120 s), one retry, progress output for each claim, and a recorded error instead of a stalled run. Restart finished in about 40 minutes with 0 errors. | **Done** |
| Starter judge | 13 claims have no fetchable source text, so they cannot be judged. | Failed fetches are cached as empty and reported as "no source text". Retry failed URLs with a second fetch method. | **Open** |
| Calibration (26 claims, starter sample) | Judge agreed with my labels on 24 of 26 (92%). Both disagreements are contradictions the judge should have called not stated: "YouTrack includes all features at no extra charge" and "Linear raised prices in 2025" (the source gives the price change but no year). My labels were not blind to the judge's verdict, so this is not independent. | Recorded in `eval/calibration/labels-claude.json`. Needs a blind human pass before quoting the rate. | **Partial** |
| Starter judge | 4 claims were marked contradicted. Two are close calls: "Linear raised prices in 2025" and "YouTrack includes all features at no extra charge". The judge may be wrong on these. | Hand-label a sample of about 50 claims, including these four, and measure judge agreement before quoting the contradiction rate. | **Open** (calibration) |
| Starter judge | 30 claims are "not stated". Some are inferences the starter made from uncited or loosely cited text. | Report them separately, as "not supported by the cited source", not as false. | **Open** |
| Evaluator judge | 3 claims not stated and 1 with no source text. | Same fixes as above. The evaluator's remaining misses are a source-coverage problem, not a citation-format one. | **Open** |
| Both | The judge and the generator are the same model family, so the judge may be lenient toward its own wording. | Judge with a different model when one is available, and compare verdicts on the same claims. | **Open** |

### Pricing check and source filter (branch `pricing-verification`)

| Problem | Fix | Status |
|---|---|---|
| Pricing claims were checked only offline, so a wrong price reached the PM unchecked. | Before the brief is written, each price in a pricing claim must appear in the full text of its cited page (Tavily extract). A claim that fails moves to "Unsupported", naming the missing figure. Pages that cannot be fetched keep the claim, labeled "(price check unavailable)". | **Done** for prices. Live on Linear: 6 price claims checked, 1 failed ($5,000 range). |
| The brief wrote prices as words ("ten dollars"), which the check could not read. | The brief prompt now requires digits with a dollar sign. | **Done** |
| Off-topic sources (Nintendo emulators, Spirit Airlines, airplane lists) reached the brief through the status searches. | Each result must name the product or one of its similar products, as a whole word, capitalized. The count of dropped results is in `run.json` as `off_topic_dropped`. Live on Linear: 27 dropped, 0 off-topic sources left. | **Done.** Limit: a product name used as a common word in a relevant article can still match. |

## Phase 4 results, eight PM tools (aggregated by `eval/aggregate.py`)

| Product | Starter supported | Starter contradicted | Evaluator supported | Evaluator contradicted | Evaluator prices in cited text |
|---|---|---|---|---|---|
| Linear | 65% | 3% | 88% | 0% | 88% |
| Jira | 63% | 3% | 84% | 0% | 86% |
| Plane | 44% | 3% | 79% | 0% | - |
| Shortcut | 76% | 1% | 89% | 0% | 100% |
| ClickUp | 60% | 9% | 77% | 0% | 100% |
| Asana | 76% | 11% | 84% | 5% | 100% |
| Trello | 69% | 6% | 89% | 7% | 100% |
| YouTrack | 69% | 4% | 92% | 3% | 100% |

### Problems from this run, and fixes

| Problem | Fix | Status |
|---|---|---|
| Evaluator contradictions are not zero everywhere: Trello 7%, Asana 5%, YouTrack 3%. | Read the contradicted claims for these three products before quoting them. Some may be judge errors, as in the calibration sample. | **Open** |
| Plane's evaluator price check is missing (no pricing claims with figures). | Check the brief for Plane. A missing check can mean the claims were phrased without figures, or that the figures were filtered out. | **Open** |
| Linear, Jira, and ClickUp briefs predate the price check and the source filter. | Rerun those three evaluator briefs when the user asks. | **Open** |
| The judge reads 20,000 characters per page, with the calibration result of 24/26 on Linear's starter sample only. | Blind human labeling on a sample from every product. | **Open** |

### Step 3: show less (verified pricing only)

| Problem | Fix | Status |
|---|---|---|
| Competitive and reception claims read as facts in the brief, but nothing checks them against a reference. | Those sections are headed "(not yet verified)", carry a note that they are leads, and tag each claim "(unverified)". Pricing is unchanged. | **Done.** Competitive and reception claims still need a reference to be verified. |

## Evaluation strategy

### What the 26 calibration claims are for

- **Judge regression test.** The 26 claims (`eval/calibration/labels-playwright.json`) are a fixed regression set. Rerun the judge on them whenever the judge model, prompt, or page limit changes. If agreement with the labels drops, the change made the judge worse, whatever product it was tested on.
- **Not a test of new products.** The 26 claims come from one product (Linear), mostly pricing, and were used to choose the judge model. They say nothing about other products or about competitive and reception claims.

### Strategy for a new product

1. **Pricing ground truth (automatic, no labels).** Capture the vendor's pricing page with Playwright and record its prices in `eval/golden/ground_truth.json`. The price check and the ground-truth recall then measure pricing accuracy without human labels. This works only where a vendor pricing page exists.
2. **Per-product blind sample.** Take 10 to 15 claims from the new product's brief, including competitive and reception claims, and label them blind with the rubric in `eval/calibration/blind-labels.xlsx`. This gives the judge's agreement for that product.
3. **Regression check.** Rerun the judge on the 26 calibration claims, and compare with the stored result (23 of 26 with the two-check rule, 24 of 26 without it).
4. **Report per product.** Support rate, contradiction rate, price accuracy against ground truth, and judge agreement with the blind sample, each with its sample size.

### Gaps

- Competitive and reception claims have no ground truth, so only the blind sample can test them.
- The current 26 do not cover those claims, so the judge's reliability on them is unmeasured.
- Only seven of the eight PM tools have price facts in the ground truth. Shortcut's prices were not captured.
- All labels so far were made by an AI reviewer, and some after seeing the judge's verdicts. A blind human pass is still needed.

## Decisions and trade-offs

Each decision lists what we chose, the cost, and what we would change next.

1. **Fixed query plan, not LLM-generated queries.** Runs are comparable and cheap. Cost: the plan does not adapt to the product category. Change: category-specific query templates, or model-proposed queries that are logged.
2. **Check that source IDs exist, not that they support the claim.** Cheap and deterministic. Cost: a real source can still be cited for the wrong claim, which the spot checks found. Change: an LLM or human check of each claim against its cited text (the Phase 4 eval).
3. **Raise the output limit.** A one-line fix. Cost: higher use per run, not yet measured. Change: compare shorter output settings on the same inputs.
4. **Paraphrase claims with no quotation marks.** Readable, fewer copied passages. Cost: paraphrases are harder to check than exact quotes. Change: keep short quotes for numbers and names.
5. **LLM status judge instead of keyword matching.** Fewer false exclusions. Cost: the judge can call a rumor "active". Change: "active" requires a dated source saying the product is sold; everything else is "unknown".
6. **Flag undated sources, then require dates for time-sensitive sections.** Stale articles no longer appear as current reception. Cost: thinner sections, and the rule depends on news mode returning dates, which is not yet verified. Change: confirm news mode on a live run, then apply a date check to pricing too.
7. **Scope: no audience demand.** Each claim can be checked against a web source. Cost: the brief does not say what customers want or will pay, which a launch decision needs most. Change: survey or sales data, which search cannot provide.

## Log

- **Date:** 2026-10-18
  - Listed the starter's shortcomings from the code review (Phase 1).
  - Added the changes, evidence, and remaining gaps for each shortcoming. Recorded the decisions and trade-offs from the Linear runs and the date-filter work.

## Maturity work (2026-10-19)

Response to the solution review. Each item lists the change, and its status.

| # | Item | Change | Status |
|---|---|---|---|
| 1 | Verification depth | Every supported claim is judged against the full text of its cited pages inside the run. Claims the judge rejects move to unsupported with the verdict. The writer sees 1,500 characters per source (was 600). | **Done** in code, tested with fake judges. Live effect measured in the variance runs below. |
| 2 | Judge validity | A 50-claim blind sheet (`eval/tune/blind-sheet.csv`) is prepared. The five contradictions are included, plus 45 claims drawn at random. The verdict key stays local, in `eval/tune/blind-key.json`. | **Open.** Needs a human to label the sheet. Agreement is not measured until it is labeled. |
| 3 | Judge and writer share a family | The in-run judge is `deepseek-ai/DeepSeek-V4-Pro`, not the Kimi writer. Set with `PIPELINE_JUDGE_MODEL`. | **Done** in code. The earlier Kimi-judged results are not re-judged yet. |
| 4 | Recommender tests | Tests for each decision rule: must-have met by a verified fact, must-have missing on the plan, price up past tolerance, price within tolerance, stale price, no price. | **Done.** 12 tests pass. Rules are tested, not outcomes against a PM's expectations. |
| 5 | Run variance | Three live Linear runs with the new pipeline (`linear-20261019-114755`, `-115209`, `-115542`). Supported claims: 28, 26, 22. Contradicted: 3, 3, 5. Not stated: 9, 5, 3. No errors. | **Partial.** Three runs of one product show the spread. Other products and more runs are not done. The contradictions come from the new judge and are not checked yet. |
| 6 | Coverage gaps | A page that comes back empty gets one retry with advanced extraction. Pricing sources are still undated. | **Partial.** Undated pricing is still open. |
| 7 | Structured output | Pricing claims are stored as fields (amounts, unit, billing) in `run.json`. Missing fields are `unknown`. | **Partial.** The brief itself is still Markdown. |
| 8 | Reliability | Tavily searches retry with backoff. The writer model retries on transient errors. Pinned `requirements.txt`. Run records include search depth and results per query. | **Partial.** The Langfuse live trace check is still open. |
| 9 | Hygiene | CI runs the 67 unit tests on every push (`.github/workflows/tests.yml`). Playwright logs untracked. `eval/store/` renamed to `eval/data/` to clear its collision with `eval/store.py`. | **Done.** The stale remote branches are left for you to decide. |
