---
name: deck-brief
description: Extract audience, objectives, claims, and evidence from source material for a new Deck Master brief.
---

# Deck Brief

<!-- skill-os-contract:v1 -->

## Use When
Turn raw material and research into deck brief inputs.

## Do Not Use
For other tasks, use the task route in [deck-master](../deck-master/SKILL.md).

## First Checks
Use current run state and available results; inspect only missing or affected inputs.
- init handoff accepted
- context manifest available
- material inventory fresh

## Forcing Questions
Reuse confirmed answers and design decisions. Ask only for a missing decision that changes this task. Record existing authorization through the runtime when needed.

## Runtime Ownership
Deck Master stage `deck-brief`; commands preserve its artifact and approval contracts.

## Allowed Commands
```bash
deck-master build-brief --run-dir <run_dir>
deck-master workflow status --run-dir <run_dir>
deck-master run-state --run-dir <run_dir>
```

## Exit Artifacts
deck_brief, claim_map_seed

## Next Skill
deck-planner

## Stop Conditions
- blocking_question
- irresolvable_constraint
- fatal_evidence_gap

## Safety Rules
Keep internal notes out of customer-visible artifacts. Reuse current validation; rerun checks affected by changes. Client export requires approval for the current version.
