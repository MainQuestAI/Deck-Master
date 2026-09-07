# Playbook — Codex Solution Deck Run

End-to-end playbook for producing a client Solution Deck from customer context
through to an approved export queue.

This route is for a new deck. Selected-page revisions use [local edits](local-edits.md).
Reuse supplied decisions and existing authorization. The commands below are a
task sequence, not a requirement to repeat already-completed steps or ask for
confirmation at every stage.

## Prerequisites

- Deck Master skill installed (`validate-skill --target codex`).
- Workspace initialized (`init-workspace`).
- Customer context files available locally.

## Steps

### 1. Read Workspace Learning Pack

If the task needs prior project guidance and `workspace/learning/workspace_learning_pack.json` exists, read the relevant entries. Pay
attention to `frequent_failure_modes` and `agent_guidance` before proceeding.

```bash
python3 scripts/deck_master.py show-learning-pack --workspace <workspace>
```

### 2. Start Conversation

Ingest local context files and create a guided conversation run.

```bash
python3 scripts/deck_master.py start-conversation \
  --workspace <workspace> \
  --context-file <customer-material-1.txt> \
  --context-file <customer-material-2.txt> \
  --run-id <run_id> \
  --industry <industry> \
  --audience client
```

### 3. Build Brief

```bash
python3 scripts/deck_master.py build-brief --run-id <run_id>
```

### 4. Build Claim Map

```bash
python3 scripts/deck_master.py build-claim-map --run-id <run_id>
```

### 5. Import Context Pack (if generated externally)

If you have prepared a richer context pack from PDFs, meeting transcripts etc.:

```bash
python3 scripts/deck_master.py import-context-pack \
  --run-id <run_id> --input context_pack.json
```

### 6. Run Autoplan

```bash
python3 scripts/deck_master.py autoplan \
  --run-id <run_id> \
  --library-mode auto \
  --planning-mode narrative_v2
```

For production runs, auto mode must use real PPT Library results. If the
library is unavailable, repair the suite or explicitly confirm
`--allow-fixture-library-fallback` for a demo downgrade.

Or step-by-step:

```bash
python3 scripts/deck_master.py search-library --run-id <run_id>
python3 scripts/deck_master.py decide-sourcing --run-id <run_id>
python3 scripts/deck_master.py create-generation-tasks --run-id <run_id>
python3 scripts/deck_master.py build-preview --run-id <run_id>
```

### 7. Request Narrative Advice

Use when the narrative needs a separate review; skip when existing review is sufficient.

```bash
python3 scripts/deck_master.py prepare-narrative-advice --run-id <run_id>
```

Read `advisor_tasks/narrative_advice_task.json`, execute reasoning, write
`advisor_results/narrative_advice.json`, then:

```bash
python3 scripts/deck_master.py import-narrative-advice \
  --run-id <run_id> --input advisor_results/narrative_advice.json
python3 scripts/deck_master.py apply-narrative-advice \
  --run-id <run_id> --input advisor_results/narrative_advice.json
```

### 8. Produce Page Packages (SC-1)

Write the complete, concrete page content from the approved narrative —
never ship production instructions as page text.

```bash
python3 scripts/deck_master.py build-preview --run-id <run_id>
```

Then write the page packages (Producer): for every narrative beat create
`page_packages/<page_id>.json` via `production.page_builder.write_page_packages`
— conclusion as the lead body block, business implication, structured
component references. Pages without resolvable evidence or a design basis
stay `draft` until the evidence is attached; a draft package cannot enter a
production build.

### 9. Build and Render

Standard PPT Master is the default backend (managed install; a missing
backend blocks honestly instead of degrading):

```bash
python3 scripts/deck_master.py build prepare --run-id <run_id>
python3 scripts/deck_master.py build run --run-id <run_id>
python3 scripts/deck_master.py render --run-id <run_id>
```

For high-density profile runs, follow
`playbooks/ppt-deck-pro-max-handoff.md` — the builder consumes the same
approved Page Packages and the public narrative (no second storyline).

### 10. External Semantic Review (v2)

Prepare the v2 review task, execute the six-dimension review with the
host agent per `prompts/quality_reviewer.prompt.md`, import the result —
it becomes the required `semantic_review` delivery gate:

```bash
python3 scripts/deck_master.py prepare-quality-review --run-id <run_id>
python3 scripts/deck_master.py import-quality-review --run-id <run_id> --input <reviewer_result.json>
python3 scripts/deck_master.py quality-gate --run-id <run_id> customer_visible_safety
```

### 11. Targeted Repair and Re-Review

If P0/P1 findings exist: run `playbooks/codex-review-and-repair.md`,
register a targeted repair (affected pages only), re-render, and re-run the
affected reviews. A review bound to an older page-package set goes stale
automatically — re-review after content changes.

### 12. Check Next Step

```bash
python3 scripts/deck_master.py next-step --run-id <run_id>
```

### 13. Final Readiness and Delivery Approval

```bash
python3 scripts/deck_master.py final-readiness --run-dir <run_dir> --no-write
```

Do not export while final-readiness reports blockers. The final artifact
approval is hash-bound: any content change invalidates it.

### 14. Export Approved Queue

```bash
python3 scripts/deck_master.py export --run-id <run_id> --queue-type client
```

## Repair Loop

If quality gates block export, run the repair playbook:
`playbooks/codex-review-and-repair.md`.

## Post-Run

When feedback capture was requested, build a learning pack after export:

```bash
python3 scripts/deck_master.py build-learning-pack --workspace <workspace>
```

Review Desk approve/reject decisions are written back to
`assets/asset_feedback.jsonl` automatically (reviewed-revision deduped).
