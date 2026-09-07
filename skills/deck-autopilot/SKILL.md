---
name: deck-autopilot
description: Continue an authorized Deck Master workflow until completion or a concrete blocker.
---

# Deck Autopilot

<!-- skill-os-contract:v1 -->

## Use When
Continuous workflow advancement across setup, planning, sourcing, production, build, quality, review, and delivery checkpoints.

## Do Not Use
For other tasks, use the task route in [deck-master](../deck-master/SKILL.md).

Advance within the user's existing authorization. Report meaningful results or blockers without fixed role announcements. Local edits use [local edits](../deck-master/playbooks/local-edits.md); read-only diagnosis uses deck-doctor.

## First Checks
Use current run state and available results; inspect only missing or affected inputs.
- n/a (operations/orchestrator lane)

## Forcing Questions
Reuse confirmed answers and design decisions. Ask only for a missing decision that changes this task. Record existing authorization through the runtime when needed.

## Runtime Ownership
Deck Master owns run state; this skill operates only the requested task.

## Allowed Commands
```bash
deck-master workflow autopilot --mode preauthorized --run-dir <run_dir>
deck-master workflow autopilot --mode repair --run-dir <run_dir>
deck-master workflow autopilot --mode review-only --run-dir <run_dir>
deck-master workflow status --run-dir <run_dir>
deck-master run-state --run-dir <run_dir>
```

## Exit Artifacts
workflow_report, run_state, next_step

## Next Skill
(see workflow runtime)

## Stop Conditions
- user-initiated stop
- material_missing
- setup_blocked
- required handoff cannot be completed with available tools or authorization
- approval_required
- final_export_requires_approval

## Safety Rules
Keep internal notes out of customer-visible artifacts. Reuse current validation; rerun checks affected by changes. Client export requires approval for the current version.
