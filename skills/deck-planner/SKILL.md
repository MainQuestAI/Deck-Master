---
name: deck-planner
description: Plan a Deck Master narrative and page structure when creating a deck or changing its direction.
---

# Deck Planner

<!-- skill-os-contract:v1 -->

## Use When
Planning workflow for claim map, narrative plan, page tasks, and sourcing intent.

## Do Not Use
For other tasks, use the task route in [deck-master](../deck-master/SKILL.md).

## First Checks
Use current run state and available results; inspect only missing or affected inputs.
- brief handoff accepted
- claim map fresh
- page budget policy available

## Forcing Questions
Reuse confirmed answers and design decisions. Ask only for a missing decision that changes this task. Record existing authorization through the runtime when needed.

## Runtime Ownership
Deck Master stage `deck-planner`; commands preserve its artifact and approval contracts.

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
Keep internal notes out of customer-visible artifacts. Reuse current validation; rerun checks affected by changes. Client export requires approval for the current version.
