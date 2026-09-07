---
name: deck-doctor
description: Diagnose Deck Master setup or run blockers using read-only status commands.
---

# Deck Doctor

<!-- skill-os-contract:v1 -->

## Use When
Diagnostics for setup, suite readiness, workspace validity, and run blockers.

## Do Not Use
Diagnosis is read-only; report a repair command when a change is needed.

## First Checks
Use current run state and available results; inspect only missing or affected inputs.
- n/a (operations/orchestrator lane)

## Forcing Questions
Reuse confirmed answers and design decisions. Ask only for a missing decision that changes this task. Record existing authorization through the runtime when needed.

## Runtime Ownership
Deck Master owns run state; this skill operates only the requested task.

## Allowed Commands
```bash
deck-master doctor --run-dir <run_dir>
deck-master workflow status --run-dir <run_dir>
deck-master run-state --run-dir <run_dir>
```

## Exit Artifacts
doctor_report, setup_status, run_state

## Next Skill
(see workflow runtime)

## Stop Conditions
- user-initiated stop

## Safety Rules
Keep internal notes out of customer-visible artifacts. Reuse current validation; rerun checks affected by changes. Client export requires approval for the current version.
