# Enhancements

Shortcomings of the starter (`starter_agent.py`), what we build to address each one, and status. Process and timeline live in `PROGRESS.md`.

Status values: `Open`, `In progress`, `Done`, `Deferred`.

## Shortcomings found in the starter

| # | Shortcoming | Why it matters | Planned fix | Status |
|---|---|---|---|---|
| 1 | Citations are optional. The system prompt says "include source URLs when available." | Answers can make claims with no verifiable source. | Require numbered citations tied to the URLs Tavily returned. Flag any claim without a source. | In progress (built in `evaluator.py`; checks that IDs exist, not that sources support claims) |
| 2 | Tool results are printed, not stored. | Nothing can be evaluated after a run, so there's no evidence of verification. | Save each run's query, results, and answer as a structured record. | In progress (`run.json` per run; not yet verified live) |
| 3 | No eval loop. | We can't show whether answers are correct or supported. | Build a test set of 10–15 cases and score citation support and accuracy. Report before and after numbers. | Open |
| 4 | Output is free text. | Downstream code (or a reviewer) can't check fields such as price. | Return a structured schema (for example, a comparison table with price, plan, billing period, and source URL). | Open |
| 5 | `truncate` only affects display. The model sees full tool results. | Long results can waste context, and the display can hide what the model used. | Trim or select results before they reach the model, and log what was passed. | Open |
| 6 | No query planning. One user question is sent as-is. | Broad questions get shallow coverage. | Break a request into one search per product and per attribute, then merge the results. | In progress (fixed plan in `plan_searches`; not yet verified live) |
| 7 | No retries or error handling beyond one generic catch. | A single failed call ends the run. | Handle empty and failed searches with clear messages. Retry with backoff where it helps. | Open |
| 8 | Observability is console output only. | Hard to debug a bad answer after the fact. | Add tracing (LangSmith or OpenTelemetry) for each step. This is the bonus item. | In progress (Langfuse added to `evaluator.py`; live trace not yet checked) |
| 9 | Model and tool settings are hard-coded or defaulted (`moonshotai/Kimi-K2.6`, `TavilySearch()` with defaults). | Results depend on settings we never chose on purpose. | Make search depth, result count, and model explicit options, and record them in each run. | Open |
| 10 | No tests. | Changes can break behavior without anyone noticing. | Add a small set of tests for parsing, formatting, and the schema. | In progress (15 unit tests for planning, dedup, parsing, citation check, rendering pass) |
| 11 | Search window doesn't match the question. The baseline used `time_range: "month"` for "this year," and the query said "2025" while it's October 2026. | The answer covers one month of news and misses the rest of the year. | Choose the time range from the question (or ask for it), and check that the query's dates match today. | Open |

### Evidence from the baseline run (`baseline/starter_output.txt`)

- Citations (item 1): the answer has a source list at the end, but most specific figures have no link next to them (Pew click rates, AI Mode share, 161.5M user forecast). Sources are not mapped to claims.
- Results (item 2): five results came back, four are listed in the answer, and the terminal truncates the rest.
- Query (item 6): one search, no planning.

## What we build (scope)

Product plus aggregated similar products, with pricing as the first focus. The enhancements above are the means. Items 1, 2, 3, and 4 are the core. Items 6 and 8 come next. The rest are optional if time runs short.

## Log

- **Date:** 2026-10-18
  - Listed the starter's shortcomings from the code review (Phase 1, in progress).
