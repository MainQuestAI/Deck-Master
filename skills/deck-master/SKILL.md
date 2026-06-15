---
name: deck-master
description: Professional Solution Deck Run OS for turning customer context, briefs, historical deck assets, sourcing decisions, quality gates, external agent handoffs, review cockpit state, benchmark runs, and delivery feedback into auditable solution deck workflows. Use when Codex needs to create or resume a Deck Master run, generate a preview from a brief, inspect next steps, run deck quality gates, import narrative advice or external reviews, manage PPT Library or PPT Deck Pro Max handoffs, export approved page queues, validate benchmark cases, or operate the local Deck Master CLI and Review Cockpit.
---

# Deck Master

Use Deck Master as the runtime and review layer for professional solution decks.
It owns run state, artifacts, typed events, sourcing decisions, quality gates,
external tool handoffs, benchmark reports, and the localhost Review Cockpit.

When a user names Deck Master, treat it as the top-level orchestrator for the
run. Even for heavy edits and external tool calls, the source of truth stays in
Deck Master state.

## Entry Points

Prefer the installed CLI:

```bash
~/.deck-master/bin/deck-master <command> [options]
```

When working inside the development repo, this is also valid:

```bash
python3 scripts/deck_master.py <command> [options]
```

The local Review Cockpit normally runs at:

```text
http://127.0.0.1:5050
```

## First Checks

Run these in order before operating on a real deck workflow:

```bash
~/.deck-master/bin/deck-master start
~/.deck-master/bin/deck-master doctor
~/.deck-master/bin/deck-master setup-status
~/.deck-master/bin/deck-master run-state --run-id <run_id>
```

For setup tasks and repair, use:

```bash
~/.deck-master/bin/deck-master setup-status
~/.deck-master/bin/deck-master --help
~/.deck-master/bin/deck-master validate-skill --target codex
curl -sf http://127.0.0.1:5050/api/runs
```

If `setup-status` is not `ready`, run setup before creating or changing a real
Deck run:

```bash
~/.deck-master/bin/deck-master setup \
  --workspace <workspace> \
  --repair-workspace \
  --target codex
```

## Core Production Flow

For real production workflows, run through setup and workspace binding before any
generation or export step:

```bash
~/.deck-master/bin/deck-master setup --workspace <path> --repair-workspace
~/.deck-master/bin/deck-master bind-workspace --run-dir <run_dir> --workspace <path>
~/.deck-master/bin/deck-master setup-status
~/.deck-master/bin/deck-master run-state --run-dir <run_dir>
```

## Core Workflow

For a brief-to-preview run:

```bash
~/.deck-master/bin/deck-master autoplan \
  --brief-file <brief.txt> \
  --industry <industry> \
  --library-mode auto \
  --run-id <run_id> \
  --force
```

Then open the Review Cockpit and inspect readiness, page decisions, evidence
coverage, external results, quality findings, and export queue.

If you manually correct a Deck plan, import the corrected plan back into the run
before using another tool:

```bash
~/.deck-master/bin/deck-master import-plan \
  --run-dir <run_dir> \
  --input <plan.md> \
  --source human
```

Before calling PPT Master, PPT Deck Pro Max, or another renderer, confirm the
run is allowed to leave Deck Master orchestration:

```bash
~/.deck-master/bin/deck-master orchestration-check --run-dir <run_dir>
```

## Common Commands

| Command | Purpose |
|---|---|
| `start-conversation` | Create a guided run from local context |
| `build-brief` | Compile a deck brief |
| `build-claim-map` | Build claim coverage input |
| `autoplan` | Run brief-to-preview pipeline |
| `search-library` | Run PPT Library selection |
| `decide-sourcing` | Decide reuse/adapt/generate per page |
| `create-generation-tasks` | Create PPT Deck Pro Max task packages |
| `build-preview` | Build preview manifest |
| `quality-gate` | Run deck quality gates |
| `next-step` | Resolve the next recommended action |
| `export` | Export approved page queue |
| `benchmark-run` | Run a local benchmark case |
| `benchmark-report` | Rebuild benchmark report for a run |
| `benchmark-rc-report` | Build RC-ready benchmark report |
| `setup` | Configure first-run Deck Master runtime |
| `setup-status` | Check setup readiness |
| `doctor` | Show setup / run diagnostics |
| `run-state` | Resolve canonical run state |
| `orchestration-check` | Check run completeness before external production |
| `bind-workspace` | Bind an existing run to workspace |
| `import-plan` | Import a human or Agent plan override |
| `import-render-result` | Import PPT Master or renderer handback |

## References

Read only the relevant file when needed:

- `references/agent-instructions.md` for detailed agent workflow rules.
- `playbooks/codex-run-solution-deck.md` for end-to-end production runs.
- `playbooks/codex-review-and-repair.md` for review and repair loops.
- `playbooks/ppt-library-handoff.md` for PPT Library handoffs.
- `playbooks/ppt-deck-pro-max-handoff.md` for generation handoffs.
- `playbooks/external-quality-review.md` for external review tasks.
- `playbooks/workspace-learning.md` for workspace learning packs.
- `schemas/*.json` for artifact contracts.
- `prompts/*.prompt.md` for task prompts prepared for external agents.

## Rules

- Keep Deck Master provider-free; do not add LLM API calls or secrets.
- When a user names Deck Master, treat it as the top-level orchestrator.
- Do not complete core deck planning, generation, quality review, or delivery only outside the Deck Master run.
- Import manual plan corrections and external tool results back into Deck Master before final reporting.
- Use Deck Master CLI commands to mutate run state.
- Do not write directly to `events.jsonl`.
- Use `--run-id` or `--run-dir` to scope every operation.
- Run `next-step` when the correct next action is unclear.
