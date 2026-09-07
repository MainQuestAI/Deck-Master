---
name: deck-review
description: Assess Deck Master delivery readiness and export an approved version when requested.
---

# Deck Review

<!-- skill-os-contract:v1 -->

## Use When
Review, repair, export readiness, and delivery checks.

## Do Not Use
For other tasks, use the task route in [deck-master](../deck-master/SKILL.md).

## First Checks
Use current run state and available results; inspect only missing or affected inputs.
- quality handoff accepted
- final artifacts present
- final readiness computable

## Forcing Questions
Reuse confirmed answers and design decisions. Ask only for a missing decision that changes this task. Record existing authorization through the runtime when needed.

## Runtime Ownership
Deck Master stage `deck-review`; commands preserve its artifact and approval contracts.

## Allowed Commands
```bash
deck-master final-readiness --run-dir <run_dir> --no-write
deck-master export --run-dir <run_dir>
deck-master workflow status --run-dir <run_dir>
deck-master run-state --run-dir <run_dir>
```

## Exit Artifacts
export_queue, final_readiness, delivery_validation

## Next Skill
client_export

## Stop Conditions
- review_rejected
- final_readiness_failed
- missing_final_approval

## Safety Rules
Keep internal notes out of customer-visible artifacts. Reuse current validation; rerun checks affected by changes. Client export requires approval for the current version.
