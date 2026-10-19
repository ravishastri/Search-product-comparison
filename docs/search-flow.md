# How many searches each system makes, and who decides

Both systems answer the same question: *"Compare Linear, an issue tracker for software teams, with its similar products, covering pricing, competitive landscape, and recent reception."* The numbers below come from the saved runs for Linear.

## Side by side

| | Starter (`starter_agent.py`) | Evaluator (`evaluator.py`) |
|---|---|---|
| **Who decides the searches** | The model. It reads the question and chooses what to search, in a loop. | Fixed code. A template turns the product, description, and category into queries. |
| **Does an LLM read the question first?** | Yes. The model interprets the question before any search. | No. The question is split into inputs (product, description, category) by the person running the command. The model is used later, to pick similar products and to write claims. |
| **Searches per question** | Varies by run. Saved Linear run: **7** tool calls. | Planned: **14**. Observed in the latest Linear run: **12** distinct queries. |
| **Results per search** | Not set in our code, so the Tavily default applies. The default (5) is not verified here. | 5 results per query, `advanced` depth. |
| **Search depth** | Not set in our code, so the Tavily default applies (believed to be `basic`; not verified here). | `advanced`. Median 3.0 s per search (`basic` measured: 1.4 s). |
| **Pages read in full** | None. The answer is built from search snippets. | Only for pricing claims: the cited pages are fetched to check the figures. |
| **Output** | Free text with links. | A brief in fixed sections, with source IDs, plus a run record. |

## What the evaluator searches, step by step

1. **Discovery (1 search).** `"<product> alternatives competitors <category>"`. The model reads the results and names up to three similar products.
2. **Status checks (1 search per candidate, up to 5).** `"<candidate> discontinued or shut down"`, limited to news from the last year. A model judges each candidate as active, retired, or unknown. Retired products are dropped. In the Linear run, the candidates were Jira, GitHub Issues, Plane, Huly, and YouTrack.
3. **Fixed plan (8 searches).**
   - Pricing: one per product and similar product (`<name> pricing plans`), so 4.
   - Competitive: one per similar product (`<product> vs <name> features`), limited to the last year, so 3.
   - Reception: one (`<product> launch reviews <year>`), limited to the last year, so 1.

Planned total: 1 + 5 + 8 = **14**. The run record shows 12 distinct queries. The difference is the searches that returned nothing usable after filtering, which leave no source behind.

## What the starter searches

The starter is a tool-calling agent. The model gets the question and a `tavily_search` tool, and it decides:
- whether to search at all,
- what to search for, and
- when it has enough to answer.

In the saved Linear run it made 7 searches. Another run could make more or fewer, because the model chooses.

## Trade-offs to state in the interview

- **Adaptive vs fixed.** The starter can follow the question wherever it goes, for example a product with no pricing page. The evaluator always runs the same plan, so a question that doesn't fit the template gets a poor plan.
- **Predictability.** The evaluator's searches are the same every time for the same inputs, which makes runs comparable. The starter's varies, so two runs can differ.
- **Cost and time.** The evaluator makes more searches, and its advanced depth is slower per call. Its extra work buys the source checks; the starter does none.
- **What is checked.** The starter builds answers from snippets with no check. The evaluator filters off-topic results, labels undated sources, and checks prices against the full cited page.
