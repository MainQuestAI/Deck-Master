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

Creating a deck without a PPT Library is the normal path: `--library-mode
auto` searches only when a library command is actually available, and the run
continues with generate decisions when it is not. Explicitly request the
library with `--library-mode real` when the task needs historical slides — it
then keeps its real dependency failure if unavailable. Fixture candidates are
only for demo/dev runs (`--library-mode fixture`); never use
`--allow-fixture-library-fallback` to mask a production dependency.

### 6b. Full-Draft Import (complete draft already written)

When you have already written the complete draft (titles, customer-visible
body, speaker notes, visual intent, citations), import it as-is instead of
regenerating content from the planning scaffold:

```bash
python3 scripts/deck_master.py import-plan --run-id <run_id> --source agent --input full_draft.json
```

`full_draft.json` carries `narrative_plan.beats` (the page set and order),
optional `page_tasks`, and a `page_packages` array — one Page Package
(`docs/contracts/page-package.v1.schema.json`) per beat with `customer_visible`
content. The import validates the whole draft before writing (page set
consistency, unique identity, complete body, citations resolvable against
`context_manifest.json`); a rejected import changes nothing. After a received
draft, pages continue production from their packages: `next-step` drives
straight to `build prepare --profile high-density`, and later updates go
through the same import (add/delete/reorder pages, change body text) with the
previous state backed up under `overrides/`.

For the high-density route, citations carry their meaning: each citation
entry should state `meaning` (what the cited source supports for this page,
sharing the page's key terms and the deck's main line), plus
`source_position` when the span matters. The builder verifies that page
claims are grounded in these citations and that numeric values trace to
them; pages below the high-density density floor are asked to add content
regions. Ids are assigned automatically, so cite sources, not evidence ids.

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

### 8. Run Quality Gates

```bash
python3 scripts/deck_master.py quality-gate --run-id <run_id> draft_v2
python3 scripts/deck_master.py quality-gate --run-id <run_id> evidence
python3 scripts/deck_master.py quality-gate --run-id <run_id> brand
```

### 9. Check Next Step

```bash
python3 scripts/deck_master.py next-step --run-id <run_id>
```

### 10. Export Approved Queue

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
