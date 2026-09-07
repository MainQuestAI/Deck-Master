---
name: deck-learn
description: Record requested Deck Master delivery feedback and build reusable learning packs.
---

# Deck Learn

<!-- skill-os-contract:v1 -->

## Use When
Use only when feedback capture or learning was requested. Delivery outcomes, reusable asset feedback, benchmark results, and workspace learning packs.

## Do Not Use
For other tasks, use the task route in [deck-master](../deck-master/SKILL.md).

## First Checks
Use current run state and available results; inspect only missing or affected inputs.
- delivery outcome recorded
- feedback events available

## Forcing Questions
Reuse confirmed answers and design decisions. Ask only for a missing decision that changes this task. Record existing authorization through the runtime when needed.

## Runtime Ownership
Deck Master stage `deck-learn`; commands preserve its artifact and approval contracts.

## Allowed Commands
```bash
deck-master record-library-feedback --run-dir <run_dir> --apply
deck-master delivery record-outcome --run-dir <run_dir>
deck-master build-learning-pack --workspace <workspace>
deck-master show-learning-pack --workspace <workspace>
deck-master workflow status --run-dir <run_dir>
deck-master run-state --run-dir <run_dir>
```

## Exit Artifacts
workspace_learning_pack, feedback_queue

## Next Skill
(terminal)

## Stop Conditions
- desensitization_failed
- delivery_not_recorded

## Safety Rules
Keep internal notes out of customer-visible artifacts. Reuse current validation; rerun checks affected by changes. Client export requires approval for the current version.
