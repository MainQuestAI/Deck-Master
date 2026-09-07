---
name: deck-setup
description: Install Deck Master skills, select global or project scope, and repair installation.
---

# Deck Setup

<!-- skill-os-contract:v1 -->

## Use When
First-run setup, suite install, workspace binding, and readiness repair.

## Do Not Use
For other tasks, use the task route in [deck-master](../deck-master/SKILL.md).

Read [installation scopes](../deck-master/references/installation.md) for project links, central upgrades, and rollback.

## First Checks
Use current run state and available results; inspect only missing or affected inputs.
- n/a (operations/orchestrator lane)

## Forcing Questions
Reuse confirmed answers and design decisions. Ask only for a missing decision that changes this task. Record existing authorization through the runtime when needed.

## Runtime Ownership
Deck Master owns run state; this skill operates only the requested task.

## Allowed Commands
```bash
deck-master setup --workspace <workspace> --repair-workspace --target codex --install-suite
deck-master setup-status --include-suite --output json
deck-master suite-status --target codex --output json
deck-master workflow status --run-dir <run_dir>
deck-master run-state --run-dir <run_dir>
```

## Exit Artifacts
setup_status, suite_status

## Next Skill
(see workflow runtime)

## Stop Conditions
- user-initiated stop

## Safety Rules
Keep internal notes out of customer-visible artifacts. Reuse current validation; rerun checks affected by changes. Client export requires approval for the current version.
