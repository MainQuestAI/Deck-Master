# Playbook — Codex Solution Deck Run

End-to-end playbook for producing a client Solution Deck from customer context
through to an approved export queue.

## Prerequisites

- Deck Master skill installed (`validate-skill --target codex`).
- Workspace initialized (`init-workspace`).
- Customer context files available locally.

## Steps

### 1. Read Workspace Learning Pack

If `workspace/learning/workspace_learning_pack.json` exists, read it. Pay
attention to `frequent_failure_modes` and `agent_guidance` before proceeding.

```bash
python3 scripts/deck_master.py show-learning-pack --workspace <workspace>
```

### 2. Start Conversation

Ingest local context files and create a guided conversation run.

```bash
python3 scripts/deck_master.py start-conversation \
  --workspace <workspace> \
  --context-dir <path-to-customer-materials> \
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

Or step-by-step:

```bash
python3 scripts/deck_master.py search-library --run-id <run_id>
python3 scripts/deck_master.py decide-sourcing --run-id <run_id>
python3 scripts/deck_master.py create-generation-tasks --run-id <run_id>
python3 scripts/deck_master.py build-preview --run-id <run_id>
```

### 7. Request Narrative Advice

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

After export, build a learning pack so the next run benefits:

```bash
python3 scripts/deck_master.py build-learning-pack --workspace <workspace>
```
