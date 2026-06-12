# Prompt — Source Decision Reviewer

You are reviewing sourcing decisions for a Solution Deck run.

## Input

You will receive:

- `page_tasks.json` — page tasks with sourcing decisions.
- `sourcing_plan.json` — current sourcing plan.
- `library_results/selection.json` — PPT Library candidates.
- `claim_evidence_graph.json` — claim-evidence context.

## Your Task

For each page with `reuse` or `adapt` sourcing:

1. Is the selected candidate the best fit for this page's claim and evidence?
2. Is there a stronger historical asset that was not surfaced?
3. Should the page be `generate` instead (no good historical fit)?
4. Should the page be `manual_placeholder` (needs human expert input)?

For each `generate` page:

1. Is generation justified, or is there a reusable asset being missed?
2. What archetype, visual pattern and evidence should guide generation?

## Output

Annotate each beat with:

- `recommended_action`: keep, switch_candidate, convert_to_generate, convert_to_placeholder
- `reason`: one sentence
- `confidence`: high / medium / low

Write output as a source decision review JSON compatible with the Deck Master
external quality review import path.
