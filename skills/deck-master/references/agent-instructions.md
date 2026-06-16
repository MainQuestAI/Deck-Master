# Deck Master — Agent Instructions

You are operating as an external Agent (Codex, Claude Code, Hermes) using the
Deck Master skill. This file tells you how to interact with Deck Master
correctly.

## Core Principle

Deck Master owns **state, artifacts, quality gates and review workflow**.
You own **reasoning, document understanding, content generation and tool
invocation**.

Never ask Deck Master to call an LLM, parse a PDF or generate a slide.
Never bypass Deck Master's quality gates or event log.

When the user explicitly names Deck Master, Deck Master is the top-level
orchestrator for the deck workflow. You may reason, draft, and call external
tools, but every core plan correction, generation result, review gate, and
delivery artifact must be written back to the Deck Master run before you report
the work as complete.

## Before You Start

1. Confirm the skill is installed:
   ```bash
   ~/.deck-master/bin/deck-master setup-status --include-suite --output json
   ~/.deck-master/bin/deck-master suite-status --target codex --output json
   ```

2. If setup is not ready, run first-run setup:
   ```bash
   ~/.deck-master/bin/deck-master setup \
     --workspace <workspace> \
     --repair-workspace \
     --target codex
   ```

   If the workspace is unknown, ask the user for the active workspace first.
   Do not create a production run until setup is ready.

3. Check workspace health:
   ```bash
   ~/.deck-master/bin/deck-master validate-workspace --workspace <path>
   ```

4. If a workspace learning pack exists, read it first:
   ```bash
   ~/.deck-master/bin/deck-master show-learning-pack --workspace <path>
   ```

## Typical Run Flow

```text
1. start-conversation  → create run, ingest local context
2. build-brief         → compile deck brief
3. build-claim-map     → compile claim map
4. autoplan            → full brief-to-preview pipeline
   OR step-by-step:
   - search-library
   - decide-sourcing
   - create-generation-tasks
   - build-preview
5. quality-gate draft  → run draft quality gate
6. next-step           → see recommended next action
7. export              → export approved pages
```

Before moving work to PPT Master, PPT Deck Pro Max, or another external build
tool, run:

```bash
~/.deck-master/bin/deck-master orchestration-check --run-dir <run_dir>
```

If the plan was manually corrected, import it first:

```bash
~/.deck-master/bin/deck-master import-plan \
  --run-dir <run_dir> \
  --input <plan.md> \
  --source human
```

## Agent Handoff Contracts

### Context Pack (you generate, Deck Master imports)

Use schema `skills/deck-master/schemas/context_pack.schema.json`.
Import with: `python3 scripts/deck_master.py import-context-pack --run-id <id> --input pack.json`

### Narrative Advice (Deck Master prepares task, you execute, Deck Master applies)

1. Deck Master generates: `python3 scripts/deck_master.py prepare-narrative-advice --run-id <id>`
2. Read `advisor_tasks/narrative_advice_task.json`.
3. Execute reasoning and write `advisor_results/narrative_advice.json`.
4. Deck Master imports: `python3 scripts/deck_master.py import-narrative-advice --run-id <id> --input ...`
5. Deck Master applies: `python3 scripts/deck_master.py apply-narrative-advice --run-id <id> --input ...`

### External Quality Review (Deck Master prepares task, you execute, Deck Master imports)

1. Deck Master generates: `python3 scripts/deck_master.py prepare-quality-review --run-id <id> --scope semantic`
2. Read the task file in `quality_review_tasks/`.
3. Execute review and write result per schema.
4. Deck Master imports: `python3 scripts/deck_master.py import-quality-review --run-id <id> --input ...`

### Generation Handoff (Deck Master prepares, you call PPT Deck Pro Max, Deck Master imports result)

1. Deck Master generates: `python3 scripts/deck_master.py prepare-generation-handoff --run-id <id>`
2. Call PPT Deck Pro Max or PPT Master with the handoff package.
3. Write result per `generation_result.schema.json`.
4. Deck Master imports: `python3 scripts/deck_master.py import-generation-result --run-id <id> --input ...`

### Render / Delivery Handback

After PPT Master or another renderer produces SVG, PPTX, PDF, or preview
artifacts, import the handback record and run the relevant gates:

```bash
~/.deck-master/bin/deck-master import-render-result --run-dir <run_dir> --input <render_result.json>
~/.deck-master/bin/deck-master quality-gate --run-dir <run_dir> render --artifact <pptx_or_pdf>
~/.deck-master/bin/deck-master quality-gate --run-dir <run_dir> delivery --artifact <pptx_or_pdf>
```

## Quality Gates

Available gates: `draft`, `draft_v2`, `evidence`, `context-conflict`,
`confidentiality`, `brand`, `render`, `delivery`.

```bash
python3 scripts/deck_master.py quality-gate --run-id <id> draft_v2
```

P0/P1 findings block client export. Override per-finding with:

```bash
python3 scripts/deck_master.py override create \
  --run-id <id> --finding-id <fid> --severity P1 \
  --reason "..." --approver "user"
```

## Rules

- Never fabricate `schema_version` values.
- Never write directly to `events.jsonl` — use Deck Master CLI.
- Never let a README or external workbench become the only source of truth for plan corrections or final artifacts.
- If a CLI command fails, read the JSON error before retrying.
- Always use `--run-id` to scope operations to a specific run.
- When in doubt, run `next-step` to see what Deck Master recommends.
