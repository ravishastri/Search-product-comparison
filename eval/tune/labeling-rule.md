# Labeling rule for claim checks

Applies to every claim in `eval/tune/to_label.json`, and to any future claim check.

## Scope
- Use only the claim's cited URLs. Do not use other pages, other products, or general knowledge.
- Do not look at any other label or judge verdict while labeling.

## Labels

**supported**
- The cited page states the claim's core fact with the same entity, figure, unit, billing period, and date.
- Paraphrase is fine. The wording does not have to match the claim exactly.
- Qualifiers in the claim ("only", "all", "free", "unlimited") must not be contradicted by the page.

**contradicted**
- The cited page gives a different value for the same fact (a different figure, unit, billing period, date, or the opposite meaning).

**not stated**
- The cited page does not contain the fact, or contains only part of it and the missing part is one the claim relies on (for example, a range whose upper or lower figure is not on the page).
- Not the same as false.
- **Decided:** a partial match counts as not stated. If any figure, unit, billing period, or qualifier the claim relies on is missing from the page, the label is not stated.

**no source**
- The cited page could not be read (empty, blocked, or the URL is gone).

## Notes
- Add a short note for every contradicted, no source, or unclear decision.
- Where two cited pages disagree with each other, record both and label the claim against the page that states it most directly.
- A claim that cites a page that does not discuss it is not supported by that citation, even if another page does.
