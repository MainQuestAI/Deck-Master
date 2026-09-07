---
name: deck-sourcing
description: Find and select reusable slides or evidence assets for Deck Master page tasks.
---

# Deck Sourcing

<!-- skill-os-contract:v1 -->

## Use When
Historical asset sourcing and page sourcing decisions.

## Do Not Use
For other tasks, use the task route in [deck-master](../deck-master/SKILL.md).

## First Checks
Use current run state and available results; inspect only missing or affected inputs.
- planner handoff accepted
- page tasks fresh
- sourcing roots available

## Forcing Questions
Reuse confirmed answers and design decisions. Ask only for a missing decision that changes this task. Record existing authorization through the runtime when needed.

## Runtime Ownership
Deck Master stage `deck-sourcing`; commands preserve its artifact and approval contracts.

## Allowed Commands
```bash
deck-master search-library --run-dir <run_dir>
deck-master import-library-selection --run-dir <run_dir> --input <selection.json>
deck-master decide-sourcing --run-dir <run_dir>
deck-master record-library-feedback --run-dir <run_dir> --page-task-id <page> --candidate-id <candidate> --outcome <outcome>
deck-master workflow status --run-dir <run_dir>
deck-master run-state --run-dir <run_dir>
```

## Exit Artifacts
library_selection, sourcing_plan, asset_feedback

## Next Skill
deck-producer

## Stop Conditions
- blocking_question
- unresolved_permission
- missing_generation_strategy

## Safety Rules
Keep internal notes out of customer-visible artifacts. Reuse current validation; rerun checks affected by changes. Client export requires approval for the current version.
