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
