# Technical statement: Search product comparison

## What it does

Given a product, the system finds similar products, searches for their pricing, competitors, and recent reception, and writes a brief in which every claim cites its source. For PM tools it also stores verified prices and SSO facts, and recommends whether to renew, negotiate, review alternatives, or wait for data, with a confidence score and the factors behind it.

## Approach

The starter code runs one search and one model reply, and nothing checks the answer. Our work adds checks at each step, and each run is recorded so it can be audited.

1. **Plan.** A fixed query plan: one pricing search per product, one comparison per similar product, and one reception search limited to the past year. Similar products are checked for shutdown with their own searches, and a model judges each one as active, retired, or unknown.
2. **Filter.** Results must name the product in scope. Reception and competitive results must have a published date within the window.
3. **Write.** The writer sees the first 1,500 characters of each source and must cite source IDs. Claims with no valid ID go to an "unsupported" section.
4. **Check prices.** Each price in a pricing claim must appear in the full text of its cited page (fetched with Tavily extract). A claim that fails moves to unsupported.
5. **Judge.** Each remaining claim is checked by a second model against the full text of its cited pages. The judge must quote the evidence verbatim, and a quote that is not in the page is not trusted. Only "supported" keeps a claim as written. The judge's default is Kimi, which scored best in our blind check.
6. **Store.** Verified prices go into a price history. A price is stored only if it has a unit, a billing period, a currency, a source, and a supported verdict. Anything else goes to a review queue. Changes raise an alert.
7. **Recommend.** The recommender reads the verified price, the purchase history, the verified SSO facts, and an editable memory file (budget and must-have features). Each rule is shown with its evidence.

Retries cover search and model calls. Failures are recorded per run instead of stopping it. Tracing with Langfuse shows each run, each search, and each model call.

## Why these choices

- **Full-text checks over snippets.** A source can exist and still not support its claim, so the check reads the page itself.
- **A second model as judge.** A model judging its own wording may be lenient, so the judge is a separate model. In our blind check the judge that agreed best with the labels was the writer's own family (Kimi). We tested DeepSeek and Qwen as alternatives, and they scored lower. We have not measured whether same-family judging is biased in general.
- **Rules over model judgment for purchases.** Budget, must-have, and price-change decisions are plain rules, so each result can be explained and checked.

## Results

On Linear, the starter's claims were 65% supported and 3% contradicted. Our evaluator's were 88% supported and 0% contradicted. The two produced different numbers of claims (135 against 34), so the rates are compared, not the counts.

Across eight PM tools, from an earlier run of the pipeline: our support rate ran from 77% to 92%, and the starter's from 44% to 76%. Our contradiction rate was lower than the starter's on seven of eight products. Trello was the exception, at 7% against the starter's 6%.

Three Linear runs with the current pipeline gave 28, 26, and 22 supported claims, with no errors.

In the blind check, one person labeled 50 claims against their pages. The judge agreed with 39 of 50 labels as first recorded. After the five contradictions were read against their pages, agreement was 43 of 50 (86%). The judge was right on four of the five contradictions. Comparing judges on the same 50 claims gave Kimi 43, DeepSeek 38, and Qwen 37.

On purchases, no plan reached renew or negotiate. The main reasons were that SSO is on higher plans only, some plans have no public price, and one tool (YouTrack) has no SSO on the pages checked.

## AI output and how it was checked

- Judge verdicts were checked by a person on a 50-claim sample. Five contradictions were read against their cited pages, and the labels were corrected where the judge was right.
- Price claims are checked against the full text of their cited pages before they reach the brief.
- SSO facts were checked against the vendor pricing pages, with the quote stored beside each fact.
- Every run record lists the models used, the sources, the verdict counts, and any errors.

## Limits

- **Sample size.** Accuracy is measured on one 50-claim sample labeled by one person. There is no measurement across the full set of claims, and no second labeler.
- **Products rerun.** Only Linear has been rerun with the current pipeline. The other seven products' results predate the latest changes.
- **Recommender tests.** The rule tests were removed because they depended on local databases that CI does not have. The rules are not under automated test.
- **Enterprise prices.** Some enterprise plans are contact-sales only, so the recommender has no price for them.
- **Prototype status.** This is a strong prototype with an evaluation harness. It is not production software.

## Where to look

- `README.md`: setup, run commands, layout, and the architecture diagram.
- `ENHANCEMENTS.md`: each shortcoming, the change made, the evidence, and the status.
- `PROGRESS.md`: the timeline and decisions.
- `eval/tune/blind-results.md`: the blind check and the judge comparison.
- `runs/`: the output and record of each run.
