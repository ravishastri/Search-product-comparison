# Enhancements

The starter (`starter_agent.py`) answers a product question with a search and a model reply. Its answers look sourced, but nothing checks them. This document lists each shortcoming we found, the change we made, the evidence that the change altered the output, and what is still not solved. Process and timeline live in `PROGRESS.md`.

The goal is not a guarantee of truth. The goal is that every claim in the output can be traced to a source, a date, and a check, and that known failures are visible instead of hidden.

Status values: `Open`, `Partial`, `Done`, `Deferred`.

## Shortcomings in the starter, and what we changed

| # | Shortcoming in the starter | Why it misleads | Change we made | Evidence | Status / what's still missing |
|---|---|---|---|---|---|
| 1 | Citations are optional. The system prompt says "include source URLs when available." | Figures appear with no link to any source. | Every claim must cite source IDs (S1, S2, ...) that the search returned. Claims with no valid ID go to an "Unsupported" section. | In the baseline, specific figures (Pew click rates, AI Mode share, 161.5M forecast) had no link. In the BMW i4 run, all 69 sources have IDs and claims cite them. | **Partial.** The check confirms IDs exist, not that the source supports the claim. Spot checks found support gaps (see row 3). |
| 2 | Tool results are printed, not stored. | Nothing can be audited after a run. | Each run writes `brief.md` and `run.json`: queries, every source with URL and date, status verdicts, errors, and the model used. | Run records were used to diagnose a truncated reply (`finish_reason=length`) and to trace the source behind each claim. | **Done** for storage. Search settings are not yet recorded per run (row 9). |
| 3 | No eval loop. Nothing measures whether answers are correct. | We cannot say how often the output is wrong. | Manual spot checks of pricing, reception, and status claims against the full text of the cited pages. | Spot checks on Linear and BMW i4 runs found: a 2022 comment presented as recent, a price from a pre-pause article presented as current, a 2020 "discontinued" article presented as current, a rumor marked "active", and one overstated claim ("prepaid" credits). | **Open.** The spot checks are manual and cover a few claims. The Phase 4 test set (5–10 launches, scored) is not built. |
| 4 | Output is free text. | Code and reviewers cannot check fields such as price or plan. | Claims are structured JSON with dimension, text, and source IDs before they are rendered. | Unsupported claims are separated automatically. | **Partial.** The brief is still Markdown. Prices are not parsed into fields. |
| 5 | `truncate` affects only display. The model sees full tool results. | The display can hide what the model used. | The model receives each source's snippet, capped at 600 characters, and the run records the sources. | Source IDs in the brief map to records in `run.json`. | **Partial.** The cap means the model sees less than the full result. We do not log which snippet text was sent. |
| 6 | No query planning. One question is sent as-is. | Broad questions get shallow coverage. | A fixed plan: one pricing search per product, one comparison per similar product, and one reception search. Similar products are checked for status with their own searches. | Live runs found three similar products each time. The status step excluded Height as retired, citing a source that says it went offline. | **Partial.** The plan is the same for every product, which hurt the BMW i4 run (software-style pricing queries). Query templates per category are not built. |
| 7 | No retries or error handling beyond one generic catch. | One failed call ends the run. | Each failed step is recorded in `errors` and the run continues. Empty model replies raise a specific error with the finish reason and token counts. | `run.json` recorded the first-attempt empty reply on run `linear-20261018-112447`, which made the cause visible. | **Partial.** No retries with backoff yet. |
| 8 | Observability is console output only. | A bad answer cannot be debugged after the run. | Langfuse traces: one root trace per run, a span per search, and a generation per model call. Tracing turns off without keys. | The Langfuse dashboard was read through Playwright. It shows 10 traces and 155 observations, with 3 errors. | **Partial.** The error observations have not been identified, and the trace view has not been used to fix a specific failure. |
| 9 | Model and search settings are hard-coded or defaulted. | Results depend on settings no one chose on purpose. | The model can be set with `--model`. Each run records the model name. Search depth is fixed at `advanced`, and results per query at 5. | `run.json` records the model. | **Partial.** Search depth and result count are not options and are not recorded. |
| 10 | No tests. | Changes can break behavior silently. | 28 unit tests: query planning, source dedup and date rules, parsing, citation checks, status parsing, and brief rendering. | All 28 pass on the current code. | **Partial.** Tests check logic, not whether claims are true. |
| 11 | Search window does not match the question. The baseline used a one-month window for a yearly question, and the query said 2025 in October 2026. | The answer covers the wrong period. | Reception and competitive searches use a 365-day window from today, with the year taken from today's date. Those searches use Tavily news mode and require a published date. | Unit tests check the window and the news-mode setting. | **Partial.** Not yet verified that news mode returns dates on a live run. If it does not, these sections will be empty. |

## Problems found while building (not in the starter's list)

These came from checking the outputs, after the starter review. Each one is a way the output could mislead a reader.

- **Empty brief.** The model used its whole output budget on reasoning and returned no text. Fixed by raising the output limit from 16,384 to 32,768 tokens. Cost: longer calls. We have not compared a model without long reasoning.
- **Retired products treated as similar products.** Height (shut down) was recommended as a similar product. A keyword check excluded it, but also falsely excluded Jira, YouTrack, and Plane (matched inside "airplanes" and an unrelated "shutdown" phrase). Replaced with a status judge that reads each candidate's results. Remaining error: the judge marked the BYD Seal and Kia EV6 "active" from a rumor and an unverifiable post. "Unknown" would have been correct.
- **Stale sources presented as current.** A 2022 Hacker News comment appeared in "recent reception." A 2020 article about a discontinued Tesla model was cited as current. The fix: reception and competitive searches use news mode and drop results with no published date. Pricing is not filtered, so a 2025 price (S41) can still appear as current.
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
| Starter baseline (Linear) | Blocked: the starter also needs the Nebius key, and my session's key is rejected. The user's terminal has a working key. | Run `starter_agent.py` in the user's terminal, saving to `eval/runs/starter/linear.txt`. | **Open**, pending the run. |
| Environment | `.env` Nebius key is rejected here (401, then "Invalid HTTP request"), while the key in the user's shell works. | Run the evaluator from the user's terminal, or re-enter the key in `.env`. | **Open.** |
| All runs | The judge checks 600-character snippets, not full pages, so "not in cited text" can mean "not in the snippet". | Fetch and store full page text for each cited source, then judge against that. | **Open**, the highest-priority fix. |

## Decisions and trade-offs

Each decision lists what we chose, the cost, and what we would change next.

1. **Fixed query plan, not LLM-generated queries.** Runs are comparable and cheap. Cost: the plan does not adapt to the product category. Change: category-specific query templates, or model-proposed queries that are logged.
2. **Check that source IDs exist, not that they support the claim.** Cheap and deterministic. Cost: a real source can still be cited for the wrong claim, which the spot checks found. Change: an LLM or human check of each claim against its cited text (the Phase 4 eval).
3. **Raise the output limit instead of changing the model.** A one-line fix. Cost: higher token use per run, not yet measured. Change: compare a model without long reasoning on the same inputs.
4. **Paraphrase claims with no quotation marks.** Readable, fewer copied passages. Cost: paraphrases are harder to check than exact quotes. Change: keep short quotes for numbers and names.
5. **LLM status judge instead of keyword matching.** Fewer false exclusions. Cost: the judge can call a rumor "active". Change: "active" requires a dated source saying the product is sold; everything else is "unknown".
6. **Flag undated sources, then require dates for time-sensitive sections.** Stale articles no longer appear as current reception. Cost: thinner sections, and the rule depends on news mode returning dates, which is not yet verified. Change: confirm news mode on a live run, then apply a date check to pricing too.
7. **Tracing that turns off without keys.** The tool runs without setup. Cost: a missing key is easy to miss, because the run still succeeds. Change: a mode that fails fast when tracing is required.
8. **Scope: no audience demand.** Each claim can be checked against a web source. Cost: the brief does not say what customers want or will pay, which a launch decision needs most. Change: survey or sales data, which search cannot provide.

## Log

- **Date:** 2026-10-18
  - Listed the starter's shortcomings from the code review (Phase 1).
  - Added the changes, evidence, and remaining gaps for each shortcoming. Recorded the decisions and trade-offs from the Linear and BMW i4 runs and the date-filter work.
