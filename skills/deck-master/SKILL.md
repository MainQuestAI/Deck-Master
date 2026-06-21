---
name: deck-master
description: Professional Solution Deck Run OS for turning customer context, briefs, historical deck assets, sourcing decisions, product capability handbacks, quality gates, review cockpit state, benchmark runs, and delivery feedback into auditable solution deck workflows. Use when Codex needs to create or resume a Deck Master run, generate a preview from a brief, inspect next steps, run deck quality gates, import narrative advice or review findings, manage PPT Library, PPT Master, PPT Deck Pro Max, or PPT Quality Gate handbacks, export approved page queues, validate benchmark cases, or operate the local Deck Master CLI and Review Cockpit.
triggers:
  - deck master
  - create a deck master run
  - resume a deck run
  - inspect deck next steps
  - review cockpit
---

# Deck Master

Use Deck Master as the runtime and review layer for professional solution decks.
It owns run state, artifacts, typed events, sourcing decisions, quality gates,
product capability handbacks, benchmark reports, and the localhost Review Cockpit.

When a user names Deck Master, treat it as the top-level orchestrator for the
run. Even for heavy edits and capability calls, the source of truth stays in
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
~/.deck-master/bin/deck-master start --run-id <run_id>
```

Read `first_action` and `next_command` from `start` before creating or changing
production artifacts. `start` includes setup readiness, suite readiness,
blocked capabilities, and the current run state when a run is provided.

For setup tasks and repair, use:

```bash
~/.deck-master/bin/deck-master setup-status --include-suite --output json
~/.deck-master/bin/deck-master --help
~/.deck-master/bin/deck-master suite-status --target codex --output json
curl -sf http://127.0.0.1:5050/api/runs
```

If `setup-status` is not `ready`, run setup before creating or changing a real
Deck run:

```bash
~/.deck-master/bin/deck-master setup \
  --workspace <workspace> \
  --repair-workspace \
  --target codex \
  --target claude-code \
  --install-suite
```

Do not stop at showing the setup command when you can run it safely. Ask the
user for the active workspace if it is missing, run setup after confirmation,
then verify setup and suite readiness again before creating a production run.

## Core Production Flow

For real production workflows, enter through setup, context intake, claim
coverage, generation session control, quality gates, review, and export:

```bash
~/.deck-master/bin/deck-master start
~/.deck-master/bin/deck-master setup \
  --workspace <path> \
  --repair-workspace \
  --target codex \
  --target claude-code \
  --install-suite
~/.deck-master/bin/deck-master start-conversation \
  --workspace <path> \
  --context-file <source.txt> \
  --industry <industry> \
  --run-id <run_id>
~/.deck-master/bin/deck-master build-brief --run-id <run_id>
~/.deck-master/bin/deck-master build-claim-map --run-id <run_id>
~/.deck-master/bin/deck-master autoplan \
  --run-id <run_id> \
  --planning-mode narrative_v2 \
  --library-mode auto
~/.deck-master/bin/deck-master generation-session create --run-id <run_id>
~/.deck-master/bin/deck-master run-generation --run-id <run_id> --dry-run
~/.deck-master/bin/deck-master render --run-id <run_id> --format html --fixture-safe
~/.deck-master/bin/deck-master quality-gate draft --run-id <run_id>
~/.deck-master/bin/deck-master run-state --run-dir <run_dir>
```

For production runs, `--library-mode auto` must use real PPT Library results.
If PPT Library is unavailable, repair the suite or explicitly confirm a demo
fallback with `--allow-fixture-library-fallback`.

If another Agent already prepared a Context Pack, create the run through Deck
Master so workspace lineage is written into `request.json`:

```bash
~/.deck-master/bin/deck-master create-run-from-context-pack \
  --workspace <path> \
  --input <context_pack.json>
```

## Core Workflow

For demo, fixture, or quick smoke runs, a brief file can still drive a preview:

```bash
~/.deck-master/bin/deck-master autoplan \
  --brief-file <brief.txt> \
  --industry <industry> \
  --run-mode fixture \
  --library-mode fixture \
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

Before calling PPT Master, PPT Deck Pro Max, or another Deck capability, confirm the
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
| `render` | Render through bundled PPT Master path |
| `render-status` | Inspect render result state |
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
| `orchestration-check` | Check run completeness before capability production |
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
- `playbooks/external-quality-review.md` for quality review tasks.
- `playbooks/workspace-learning.md` for workspace learning packs.
- `schemas/*.json` for artifact contracts.
- `prompts/*.prompt.md` for task prompts prepared for Agents.

## Rules

- Keep Deck Master provider-free; do not add LLM API calls or secrets.
- When a user names Deck Master, treat it as the top-level orchestrator.
- Do not complete core deck planning, generation, quality review, or delivery outside the Deck Master run state.
- Import manual plan corrections and capability results back into Deck Master before final reporting.
- Use Deck Master CLI commands to mutate run state.
- Do not write directly to `events.jsonl`.
- Use `--run-id` or `--run-dir` to scope every operation.
- Run `next-step` when the correct next action is unclear.
