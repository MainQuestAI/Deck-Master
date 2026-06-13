---
name: deck-master
description: Professional Solution Deck Run OS for turning customer context, briefs, historical deck assets, sourcing decisions, quality gates, external agent handoffs, review cockpit state, benchmark runs, and delivery feedback into auditable solution deck workflows. Use when Codex needs to create or resume a Deck Master run, generate a preview from a brief, inspect next steps, run deck quality gates, import narrative advice or external reviews, manage PPT Library or PPT Deck Pro Max handoffs, export approved page queues, validate benchmark cases, or operate the local Deck Master CLI and Review Cockpit.
---

# Deck Master

Use Deck Master as the runtime and review layer for professional solution decks.
It owns run state, artifacts, typed events, sourcing decisions, quality gates,
external tool handoffs, benchmark reports, and the localhost Review Cockpit.

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

Run these before operating on a real deck workflow:

```bash
~/.deck-master/bin/deck-master --help
~/.deck-master/bin/deck-master validate-skill --target codex
curl -sf http://127.0.0.1:5050/api/runs
```

## Core Workflow

For a brief-to-preview run:

```bash
~/.deck-master/bin/deck-master autoplan \
  --brief-file <brief.txt> \
  --industry <industry> \
  --library-mode auto \
  --runs-dir ~/.deck-master/runs \
  --run-id <run_id> \
  --force
```

Then open the Review Cockpit and inspect readiness, page decisions, evidence
coverage, external results, quality findings, and export queue.

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
- Use Deck Master CLI commands to mutate run state.
- Do not write directly to `events.jsonl`.
- Use `--run-id` or `--run-dir` to scope every operation.
- Run `next-step` when the correct next action is unclear.
