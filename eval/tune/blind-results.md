# Blind check: human labels vs judge (50 claims)

Labels are from `eval/tune/blind-labels-human.csv`. The judge verdicts are the earlier Kimi-judged results in `eval/results/evaluator-*-llm.json`, which the key holds. Those are not the DeepSeek runs.

- Agreement: 39 of 50 (78%).
- Labeling rule: "partially supported" was recorded as `not_stated`, per `labeling-rule.md`.
- The sample was 5 judge contradictions plus 45 random claims. The human labeled all 5 contradictions `supported`.

## Disagreements (11)

| Human | Judge | Count | What it means |
|---|---|---|---|
| supported | contradicted | 5 | The human disagrees with every judge contradiction in the sample. Either the judge is wrong, or the human is lenient. Check before trusting the contradiction rate. |
| supported | no_source_text | 3 | The human could read the page, but the pipeline could not fetch its text. A fetch gap. |
| supported | unverified_evidence | 1 | The judge's quote was not found verbatim in the page. |
| supported | not_stated | 1 | The judge missed a statement the human found. |
| not_stated | supported | 1 | The judge accepted a claim the human says the page does not state. |

Rows: B02, B08, B09, B12, B20, B25, B28, B37, B43, B44, B46.

## Check of the five contradictions

Each cited page was fetched with Tavily extract and read for the figures, names, and dates in the claim.

| Row | Claim (short) | What the page says | Judge (contradicted) | Your label (supported) | Proposed label |
|---|---|---|---|---|---|
| B08 | 55% of negative *ClickUp* reviews cite pricing | The 55% figure is in the *Monday.com* section | Right: wrong product | Wrong | contradicted |
| B09 | ClickUp paid plans $7 to $19 per user per month | $7–$19 is the annual range; monthly runs $10–$29 | Right | Wrong | contradicted |
| B28 | Trustpilot: ClickUp support takes weeks, including billing disputes | The support-delay line is in the *Monday.com* section; "billing disputes" is not on the page | Right | Wrong | contradicted |
| B44 | ClickUp competes with Asana, Monday.com, Smartsheet, **Jira**, Notion | Page lists Asana, Monday.com, Notion, Trello, **Wrike**, Smartsheet. Jira is not listed; Wrike is missing | Direction right, but "contradicted" is strong | Wrong | not_stated (partial match, per the rule) |
| B46 | Server support ends **after** Feb 15, 2024 | Page says support ends **on** Feb 15, 2024 | Right on a strict reading | Probably wrong | contradicted |

Result: the judge was right on four of the five. Your label was wrong on all five. On B44 the judge overstated a partial match, but "supported" is still wrong.

If these corrections are accepted, agreement moves from 39 of 50 (78%) to 43 of 50 (86%). The four that move to contradicted now agree with the judge. B44 still disagrees, because the judge said contradicted and the rule says not_stated.

These are proposed, not applied. Your labels in `blind-labels-human.csv` are unchanged, pending your decision.

## Corrections applied

The five corrections above are now in `blind-labels-human.csv`. `your_label_raw` keeps the original label, and `your_label` has the corrected one.

- Corrected agreement: 43 of 50 (86%). This replaces the 39 of 50 (78%) figure above.
- Remaining disagreements: the three judge `no_source_text` rows (B25, B37, B43), the `unverified_evidence` row (B02), the `not_stated` vs `supported` rows (B12, B20), and B44 (judge contradicted, corrected label not_stated).
