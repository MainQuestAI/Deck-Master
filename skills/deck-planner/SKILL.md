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


<!-- skill-os-contract:v1 -->

## Use When
Planning workflow for claim map, narrative plan, page tasks, and sourcing intent.

## Do Not Use
Do not use outside its lane in the Skill OS workflow. Do not treat a successful command return code as stage completion.

## First Checks
- brief handoff accepted
- claim map fresh
- page budget policy available

## Forcing Questions
- planner.primary_thesis: 这套 Deck 最希望受众接受的核心判断是什么？
- planner.counter_question: 受众最可能提出的反方疑问是什么？
- planner.page_budget: 页数预算是多少？
- planner.proof_order: 证据的出现顺序如何支撑核心判断？

## Runtime Ownership
Skill OS workflow runtime; stage `deck-planner`. Stage completion is validated by the contract entry/exit validator and handoff/approval runtime, not by command return code.

## Allowed Commands
```bash
deck-master autoplan --run-dir <run_dir>
deck-master workflow status --run-dir <run_dir>
deck-master run-state --run-dir <run_dir>
```

## Exit Artifacts
narrative_plan, page_tasks, sourcing_intent

## Next Skill
deck-sourcing

## Stop Conditions
- blocking_question
- page_budget_conflict
- missing_required_evidence_policy

## Safety Rules
Keep internal-only production notes out of customer-visible content. Never bypass the final client export approval. Obey the stage contract's transition policy.
