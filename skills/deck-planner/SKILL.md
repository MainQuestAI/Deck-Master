---
name: deck-planner
description: Deck Master planning entry for context intake, brief, claim map, narrative plan, page tasks, and sourcing intent inside a Deck Master run. Use when the user asks to plan a solution deck structure, turn customer material into a narrative plan, or prepare page-level production tasks.
triggers:
  - plan a solution deck
  - build deck brief
  - make a claim map
  - create a narrative plan
  - prepare page tasks
---

# Deck Planner

Use this skill for planning work inside Deck Master.

## First Checks

Start with Deck Master readiness:

```bash
~/.deck-master/bin/deck-master setup-status --include-suite --output json
```

If setup, workspace, or required suite readiness is blocked, return to the
Deck Master setup ceremony before creating production artifacts. Explain the
missing readiness in normal language, confirm the intended workspace when
needed, run safe setup or repair commands, and verify status again.

## Runtime Ownership

Deck Master run state owns production planning. Do not create final narrative
plans, page tasks, or sourcing decisions outside a Deck Master run.

## Allowed Commands

```bash
~/.deck-master/bin/deck-master start --run-dir <run_dir> --run-id <run_id>
~/.deck-master/bin/deck-master build-brief --run-dir <run_dir> --run-id <run_id>
~/.deck-master/bin/deck-master build-claim-map --run-dir <run_dir> --run-id <run_id>
~/.deck-master/bin/deck-master autoplan --run-dir <run_dir> --run-id <run_id> --planning-mode narrative_v2
~/.deck-master/bin/deck-master search-library --run-dir <run_dir> --run-id <run_id>
~/.deck-master/bin/deck-master decide-sourcing --run-dir <run_dir> --run-id <run_id>
```

## Forbidden Shortcuts

- Do not bypass Deck Master setup for production runs.
- Do not treat fixture autoplan output as production planning.
- Do not hand final planning work to another tool without importing the result back.

## Output Expectations

Planning output must be visible through Deck Master artifacts such as
`deck_brief.json`, `claim_map.json`, `narrative_plan.json`,
`page_tasks.json`, and `sourcing_plan.json`.
